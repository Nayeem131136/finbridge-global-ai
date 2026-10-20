"""FinBridge agent.

Two planners share the same tools, tiers and audit log:
  * LLM planner (Groq tool calling) when GROQ_API_KEY is set
  * Deterministic rule planner (offline, used for the demo fallback and the eval suite)
"""
import re
from datetime import date

from .data import CURRENCY_ALIASES, SYMBOLS
from .security import mask_pii, scan_injection
from .session import Session
from .tools import Tier, run_tool
from .util import find_dates

_CUR_WORDS = "|".join(sorted(CURRENCY_ALIASES, key=len, reverse=True))
_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_MULT = {"k": 1e3, "lakh": 1e5, "lac": 1e5, "m": 1e6, "million": 1e6}
AMT_CODE = re.compile(r"(?<![\w.])" + _NUM + r"\s*(k|lakh|lac|million)?\s*(" + _CUR_WORDS + r")\b", re.I)
AMT_SYM = re.compile(r"([$£€৳])\s?" + _NUM + r"\s*(k|lakh|lac|million)?", re.I)
CUR_RE = re.compile(r"\b(" + _CUR_WORDS + r")\b", re.I)

HELP = ("I'm FinBridge, your cross-border student finance assistant. I can: compare the cheapest way to send money or pay tuition, "
        "check FX timing, build a monthly budget, plan tuition installments, outline a credit-building roadmap, "
        "check a tuition invoice for fraud signs, and prepare a transfer that only you can confirm. "
        "Try: \"Compare the cheapest way to pay 12000 USD tuition from BDT\".")


def _num(s: str, mult: str | None = None) -> float:
    v = float(s.replace(",", ""))
    return v * _MULT[mult.lower()] if mult else v


def amounts(text: str) -> list[tuple[int, float, str]]:
    out = []
    for m in AMT_CODE.finditer(text):
        out.append((m.start(), _num(m[1], m[2]), CURRENCY_ALIASES[m[3].lower()]))
    for m in AMT_SYM.finditer(text):
        out.append((m.start(), _num(m[2], m[3]), SYMBOLS[m[1]]))
    return sorted(out)


def currencies(text: str) -> list[str]:
    seen = []
    for m in CUR_RE.finditer(text):
        c = CURRENCY_ALIASES[m[1].lower()]
        if c not in seen:
            seen.append(c)
    for m in re.finditer(r"[$£€৳]", text):
        c = SYMBOLS[m[0]]
        if c not in seen:
            seen.append(c)
    return seen


def _after(text: str, words: str, home: str):
    """Number following one of `words`, with optional currency."""
    pat = re.compile(r"\b(?:" + words + r")\b[^\d\n]{0,25}(\+?)" + _NUM + r"\s*(k|lakh|lac)?\s*(" + _CUR_WORDS + r")?\b", re.I)
    for m in pat.finditer(text):
        digits = re.sub(r"\D", "", m[2])
        if m[1] == "+" or len(digits) > 9:      # phone numbers / IDs are not amounts
            continue
        ccy = CURRENCY_ALIASES[m[4].lower()] if m[4] else None
        return _num(m[2], m[3]), ccy
    return None, None


def _purpose(t: str) -> str:
    if re.search(r"tuition|university|semester fee|college|fees? to", t):
        return "tuition"
    if re.search(r"rent|landlord|hostel", t):
        return "rent"
    if re.search(r"famil|parents|mother|father|brother|sister", t):
        return "family_support"
    if re.search(r"living|expenses|allowance", t):
        return "living"
    if re.search(r"book", t):
        return "books"
    return "tuition"


def _priority(t: str) -> str:
    if re.search(r"cheap|lowest|least|save|cost", t):
        return "cheapest"
    if re.search(r"fast|quick|urgent|instant|today", t):
        return "fastest"
    return "balanced"


class Agent:
    def __init__(self, llm=None):
        self.llm = llm   # object with .run(session, message, tool_runner) or None

    # ------------------------------------------------------------ entry point
    def handle(self, s: Session, message: str) -> dict:
        s.audit.append("user_message", {"text": message})
        flags = []
        inj = scan_injection(message)
        # invoices are legitimately allowed to contain odd text; they are parsed as data below
        is_invoice = bool(re.search(r"\b(invoice|beneficiary)\b", message, re.I)) and len(message) > 80
        if inj and not is_invoice:
            s.audit.append("security_flag", {"type": "prompt_injection", "patterns": inj})
            reply = ("I can't follow instructions that try to bypass confirmation, limits or my safety rules, "
                     "and I never move money without your own PIN confirmation. "
                     "I can still help you compare routes, plan tuition or check an invoice.")
            s.history += [{"role": "user", "content": mask_pii(message)}, {"role": "assistant", "content": reply}]
            return {"reply": reply, "cards": [], "trace": [], "pending": None,
                    "flags": [{"type": "prompt_injection", "msg": "Blocked a request that tried to override safety rules."}]}
        trace, cards = [], []

        def runner(name, args):
            res = run_tool(s, name, args, Tier.EXECUTE)
            trace.append({"tool": name, "tier": res.get("tier"), "ok": res["ok"],
                          "args": {k: (mask_pii(v) if isinstance(v, str) else v) for k, v in args.items() if k != "text"}})
            if res["ok"] and res.get("card"):
                cards.append(res["card"])
            return res

        if self.llm is not None:
            try:
                reply = self.llm.run(s, message, runner)
                mode = "llm"
            except Exception as e:   # fall back to deterministic planner if the API fails
                s.audit.append("llm_error", {"error": str(e)[:200]})
                reply, mode = self._rules(s, message, runner), "rules"
        else:
            reply, mode = self._rules(s, message, runner), "rules"

        for c in cards:
            if c["type"] == "invoice_check" and c["data"].get("injection_detected"):
                flags.append({"type": "prompt_injection", "msg": "A document contained AI-directed instructions; they were ignored."})
        pending = next((c["data"] for c in cards if c["type"] == "confirmation"), None)
        s.history += [{"role": "user", "content": mask_pii(message)}, {"role": "assistant", "content": reply}]
        return {"reply": reply, "cards": cards, "trace": trace, "pending": pending, "flags": flags, "mode": mode}

    # ------------------------------------------------------------ rule planner
    def _rules(self, s: Session, message: str, run) -> str:
        t = message.lower()
        amts = amounts(message)
        curs = currencies(message)

        # 1. invoice
        if re.search(r"\b(invoice|beneficiary)\b", t) and len(message) > 80:
            r = run("check_invoice", {"text": message})
            return r.get("summary") or r["error"]

        # 2. credit
        if re.search(r"\bcredit\b", t):
            months = re.search(r"(\d+)\s*months?", t)
            r = run("credit_roadmap", {"months_in_country": int(months[1]) if months else 0,
                                       "has_local_id": bool(re.search(r"(have|got).{0,20}(ssn|local id|id number|nid)", t)),
                                       "has_income": bool(re.search(r"(part[- ]time|job|income|salary|stipend|work)", t))})
            return r.get("summary") or r["error"]

        # 2b. saved study plan (signed-in users)
        if re.search(r"\b(my|study)\s+(study\s+)?plan\b|funding gap|how much (do|will) i (still )?need", t):
            r = run("get_study_plan", {})
            return r.get("summary") or r["error"]

        # 3. tuition plan
        if re.search(r"\btuition\b", t) and re.search(r"\b(plan|schedule|installments?|due|save|saving|saved)\b", t) \
                and not re.search(r"\b(send|compare|cheapest|transfer)\b", t):
            return self._tuition(message, amts, curs, run)

        # 4. budget
        if re.search(r"\bbudget", t):
            return self._budget(message, amts, run)

        # 5. send / pay / compare
        if re.search(r"\b(send|transfer|pay|wire|remit|compare|cheapest|cheaper|best way|route|fees?)\b", t) and amts:
            return self._route(s, message, amts, curs, run)

        # 6. fx timing / rate
        if re.search(r"\b(when|best time|timing|wait|good time|should i (convert|exchange|buy))\b", t) and len(curs) >= 1:
            return self._fx(message, amts, curs, run, timing=True)
        if re.search(r"\b(rate|convert|exchange|worth|how much is|what is|what's|whats)\b", t) and curs:
            return self._fx(message, amts, curs, run, timing=False)

        # 7. account
        if re.search(r"\b(balance|account|wallet|transactions?|history)\b", t):
            r = run("get_account", {})
            return r.get("summary") or r["error"]
        return HELP

    # ---- helpers per intent
    def _fx(self, message, amts, curs, run, timing: bool) -> str:
        frm, to = self._pair(message, curs)
        if not frm or not to:
            return "Which two currencies? For example: \"Best time to convert BDT to USD?\""
        amount = amts[0][1] if amts else (1000.0 if frm in ("BDT", "JPY", "INR") else 100.0)
        parts = []
        r = run("get_fx_rate", {"from_currency": frm, "to_currency": to, "amount": amount})
        parts.append(r.get("summary") or r["error"])
        if timing:
            r2 = run("fx_timing", {"from_currency": frm, "to_currency": to})
            parts.append(r2.get("summary") or r2["error"])
        return " ".join(parts)

    def _pair(self, message: str, curs: list[str]):
        m1 = re.search(r"\bfrom\s+(" + _CUR_WORDS + r")\b", message, re.I)
        m2 = re.search(r"\b(?:to|into|in)\s+(" + _CUR_WORDS + r")\b", message, re.I)
        frm = CURRENCY_ALIASES[m1[1].lower()] if m1 else None
        to = CURRENCY_ALIASES[m2[1].lower()] if m2 else None
        if not frm and not to and len(curs) >= 2:
            frm, to = curs[0], curs[1]
        elif frm and not to:
            to = next((c for c in curs if c != frm), None)
        elif to and not frm:
            frm = next((c for c in curs if c != to), None)
            if not frm and to != "BDT":
                frm = "BDT"
        if frm and not to and frm != "BDT":
            to = "BDT"
        return frm, to

    def _route(self, s, message, amts, curs, run) -> str:
        t = message.lower()
        amount_ccy = amts[0][2]
        amount = amts[0][1]
        frm, to = self._pair(message, curs)
        if not frm and not to:
            frm, to = ("BDT", amount_ccy) if amount_ccy != "BDT" else ("BDT", None)
        if frm is None:
            frm = "BDT"
        if to is None:
            return "Which currency should the recipient receive? For example: \"Send 800 GBP tuition from BDT\"."
        basis = "send" if amount_ccy == frm else "receive"
        if amount_ccy not in (frm, to):
            return f"The amount is in {amount_ccy}, but I need it in {frm} (what you pay) or {to} (what arrives)."
        purpose = _purpose(t)
        r = run("compare_remittance_routes", {"amount": amount, "from_currency": frm, "to_currency": to,
                                               "purpose": purpose, "basis": basis, "priority": _priority(t)})
        if not r["ok"]:
            return r["error"]
        text = r["summary"]
        wants_send = re.search(r"\b(send|transfer|pay|wire)\b", t) and not re.search(r"\b(compare|cheapest|how much|what is|cost)\b", t)
        if wants_send:
            benef = "Example University Bursar" if purpose == "tuition" and re.search(r"universit|tuition|bursar", t) else None
            if not benef:
                m = re.search(r"\bto\s+([A-Z][\w.]+(?:\s+[A-Z][\w.]+){0,3})", message)
                benef = m[1].strip() if m and m[1].lower() not in CURRENCY_ALIASES else "New recipient"
            country = "GB" if benef == "Example University Bursar" else "US"
            tr = run("request_transfer", {"quote_id": r["data"]["recommended_quote_id"], "beneficiary_name": benef,
                                          "recipient_country": country})
            text += " " + (tr.get("summary") or tr["error"])
        return text

    def _budget(self, message, amts, run) -> str:
        income, iccy = _after(message, "income|allowance|stipend|salary|earn|receive", "BDT")
        if income is None and amts:
            income, iccy = amts[0][1], amts[0][2]
        cats = ["rent", "food", "groceries", "transport", "utilities", "phone", "internet", "insurance", "books",
                "health", "entertainment", "shopping", "travel", "dining", "subscriptions", "tuition"]
        expenses, eccy = {}, None
        for c in cats:
            v, cc = _after(message, c, "BDT")
            if v is not None and c != "income":
                expenses[c] = v
                eccy = eccy or cc
        if not income or not expenses:
            return ("To build your budget I need your monthly income and a few expenses, for example: "
                    "\"Budget: income 60000 BDT, rent 20000, food 12000, transport 3000, entertainment 5000\".")
        args = {"monthly_income": income, "income_currency": iccy or eccy or "BDT", "expenses": expenses,
                "expense_currency": eccy or iccy or "BDT"}
        r = run("build_budget", args)
        return r.get("summary") or r["error"]

    def _tuition(self, message, amts, curs, run) -> str:
        total, tccy = _after(message, "tuition", "USD")
        if total is None and amts:
            total, tccy = amts[0][1], amts[0][2]
        dues = find_dates(message)
        saved, _ = _after(message, "saved|have saved|savings", "BDT")
        monthly, _ = _after(message, r"per month|monthly|each month|every month|can save", "BDT")
        if not total or not dues:
            return ("To plan your tuition I need the total and due date(s), for example: "
                    "\"Plan tuition 12000 USD due 15 Dec 2026 and 15 Mar 2027, saved 200000 BDT, can save 40000 BDT monthly\".")
        args = {"total": total, "currency": tccy or "USD", "due_dates": [d.isoformat() for d in dues],
                "saved": saved or 0.0}
        if monthly:
            args["monthly_capacity"] = monthly
        r = run("plan_tuition", args)
        return r.get("summary") or r["error"]
