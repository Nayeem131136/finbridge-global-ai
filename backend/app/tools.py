"""Tool registry with permission tiers, validated arguments and audit logging.

Tier 0 READ     : lookups only
Tier 1 SUGGEST  : produces plans/advice, changes nothing
Tier 2 EXECUTE  : can only *request* a transfer. The money moves in
                  Session.confirm(), which is called by the human via the API,
                  never by the agent.
"""
import json
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable

from pydantic import BaseModel, Field, ValidationError, field_validator

from . import budget as budget_mod
from . import credit as credit_mod
from . import fx
from . import invoice as invoice_mod
from . import remit
from . import tuition as tuition_mod
from .data import USD_RATES
from .session import Session
from .util import find_dates, fmt_money


class Tier(IntEnum):
    READ = 0
    SUGGEST = 1
    EXECUTE = 2


def _ccy(v: str) -> str:
    v = (v or "").upper().strip()
    if v not in USD_RATES:
        raise ValueError(f"Unsupported currency '{v}'. Supported: {', '.join(sorted(USD_RATES))}")
    return v


class FxArgs(BaseModel):
    from_currency: str
    to_currency: str
    amount: float = Field(1.0, gt=0, le=1e9)
    _c = field_validator("from_currency", "to_currency")(_ccy)


class CompareArgs(BaseModel):
    amount: float = Field(gt=0, le=1e9)
    from_currency: str = "BDT"
    to_currency: str
    purpose: str = "tuition"
    basis: str = Field("receive", pattern="^(send|receive)$")
    priority: str = Field("balanced", pattern="^(cheapest|fastest|balanced)$")
    _c = field_validator("from_currency", "to_currency")(_ccy)


class ExpenseItem(BaseModel):
    category: str = Field(max_length=40, description="e.g. rent, food, transport, entertainment")
    amount: float = Field(ge=0, le=1e9, description="monthly amount")


class BudgetArgs(BaseModel):
    monthly_income: float = Field(gt=0, le=1e9)
    income_currency: str = "BDT"
    expenses: list[ExpenseItem] = Field(min_length=1)

    @field_validator("expenses", mode="before")
    @classmethod
    def _dict_to_list(cls, v):          # accept {"rent": 100} from the rule planner
        if isinstance(v, dict):
            return [{"category": k, "amount": x} for k, x in v.items()]
        return v

    expense_currency: str | None = None
    savings_target_pct: float = Field(20.0, ge=0, le=90)
    _c = field_validator("income_currency")(_ccy)


class TuitionArgs(BaseModel):
    total: float = Field(gt=0, le=1e9)
    currency: str
    due_dates: list[str] = Field(min_length=1, max_length=12, description="ISO dates YYYY-MM-DD")
    saved: float = Field(0.0, ge=0)
    monthly_capacity: float | None = Field(None, ge=0)
    home_currency: str = "BDT"
    _c = field_validator("currency", "home_currency")(_ccy)


class CreditArgs(BaseModel):
    country: str = Field("your host country", max_length=60)
    months_in_country: int = Field(0, ge=0, le=240)
    has_local_id: bool = False
    has_income: bool = False


class InvoiceArgs(BaseModel):
    text: str = Field(min_length=10, max_length=8000)


class TransferArgs(BaseModel):
    quote_id: str = Field(pattern=r"^Q\d{1,4}$")
    beneficiary_name: str = Field(min_length=2, max_length=80)
    recipient_country: str = Field(min_length=2, max_length=2, description="ISO-2 country code")


class NoArgs(BaseModel):
    pass


# ------------------------------------------------------------------ tools
def t_fx(s: Session, a: FxArgs):
    r = fx.rate(a.from_currency, a.to_currency)
    out = fx.convert(a.amount, a.from_currency, a.to_currency)
    summary = (f"{fmt_money(a.amount, a.from_currency)} = {fmt_money(out, a.to_currency)} "
               f"(1 {a.from_currency} = {r:.4f} {a.to_currency}, {fx.source_label()}).")
    return {"summary": summary, "data": {"rate": r, "converted": out},
            "card": {"type": "fx_rate", "data": {"from": a.from_currency, "to": a.to_currency,
                                                 "rate": r, "amount": a.amount, "converted": out,
                                                 "source_label": fx.source_label()}}}


def t_timing(s: Session, a: FxArgs):
    t = fx.timing(a.from_currency, a.to_currency)
    summary = (f"{a.from_currency}->{a.to_currency} timing: {t['signal']} "
               f"(today's rate is at percentile {t['percentile']} of the last 30 days, 0=lowest, 100=highest; "
               f"{t['vs_avg_pct']:+.2f}% vs the 30-day average). {t['advice']}")
    return {"summary": summary, "data": {k: v for k, v in t.items() if k != "series"},
            "card": {"type": "fx_timing", "data": t}}


def t_compare(s: Session, a: CompareArgs):
    res = remit.compare(a.amount, a.from_currency, a.to_currency, a.purpose, a.basis, a.priority)
    for q in res["quotes"]:
        q["quote_id"] = s.save_quote(q, a.purpose)
    best = res["quotes"][0]
    target = (f"{fmt_money(a.amount, a.to_currency)} to arrive" if a.basis == "receive"
              else f"sending {fmt_money(a.amount, a.from_currency)}")
    summary = (f"Best route for {target} ({a.purpose}): {best['provider']}. You pay "
               f"{fmt_money(best['send_amount'], a.from_currency)}, recipient gets "
               f"{fmt_money(best['receive_amount'], a.to_currency)}, total cost {best['total_cost_pct']:.2f}% "
               f"(about {fmt_money(best['total_cost'], a.from_currency)}), arrives in about {best['speed_hours']}h. "
               f"Choosing it over the costliest option saves {fmt_money(res['savings_vs_worst'], a.from_currency)}. "
               f"Quote ID: {best['quote_id']}. Rates and fees are illustrative sandbox data.")
    return {"summary": summary, "data": {"recommended_quote_id": best["quote_id"], "quotes": res["quotes"],
                                          "excluded": res["excluded"]},
            "card": {"type": "route_comparison", "data": res | {"to": a.to_currency, "from": a.from_currency}}}


def t_budget(s: Session, a: BudgetArgs):
    res = budget_mod.build_budget(a.monthly_income, a.income_currency, {e.category: e.amount for e in a.expenses},
                                  a.expense_currency or a.income_currency, a.savings_target_pct)
    c = res["currency"]
    summary = (f"Budget: income {fmt_money(res['income'], c)}, expenses {fmt_money(res['total_expenses'], c)}, "
               f"surplus {fmt_money(res['surplus'], c)} (savings rate {res['savings_rate']:.0f}%). ")
    if res["alerts"]:
        summary += "Alerts: " + " ".join(res["alerts"]) + " "
    summary += "Tips: " + " ".join(res["tips"][:3])
    return {"summary": summary, "data": res, "card": {"type": "budget", "data": res}}


def t_tuition(s: Session, a: TuitionArgs):
    dues = []
    for d in a.due_dates:
        found = find_dates(d)
        if not found:
            raise ValueError(f"Could not read the date '{d}'. Use YYYY-MM-DD.")
        dues.append(found[0])
    res = tuition_mod.plan(a.total, a.currency, dues, s.today, a.saved, a.monthly_capacity, a.home_currency)
    h = a.home_currency
    summary = (f"Tuition plan: {fmt_money(a.total, a.currency)} in {res['installments']} installment(s). "
               f"You need to set aside about {fmt_money(res['required_monthly'], h)} per month. ")
    if res["feasible"] is False:
        summary += f"That is {fmt_money(res['gap'], h)} per month more than your capacity, so consider more installments, a scholarship office talk, or extra income. "
    elif res["feasible"]:
        summary += "Your monthly capacity covers it. "
    summary += f"FX timing: {res['fx_signal']}. Convert in {len(res['tranche_plan'])} tranche(s). Reminders are set 14 and 3 days before each due date."
    return {"summary": summary, "data": res, "card": {"type": "tuition_plan", "data": res}}


def t_credit(s: Session, a: CreditArgs):
    res = credit_mod.roadmap(a.country, a.months_in_country, a.has_local_id, a.has_income)
    summary = (f"Credit-building roadmap ({res['horizon']}): " +
               " ".join(f"{i + 1}) {st['step']}." for i, st in enumerate(res["steps"][:4])) +
               " " + res["disclaimer"])
    return {"summary": summary, "data": res, "card": {"type": "credit_roadmap", "data": res}}


def t_invoice(s: Session, a: InvoiceArgs):
    res = invoice_mod.check(a.text)
    label = {"do_not_pay": "DO NOT PAY yet", "review": "Needs review", "looks_consistent": "Looks consistent"}[res["verdict"]]
    summary = f"Invoice check: {label}. "
    if res["amount"]:
        summary += f"Amount {fmt_money(res['amount'], res['currency'])}"
        summary += f", due {res['due_date']}. " if res["due_date"] else ". "
    summary += " ".join(f["msg"] for f in res["flags"])
    public = {k: v for k, v in res.items() if not k.startswith("_")}      # the document text is not sent back to the model
    card = {**public, "text": res["_text"], "highlights": res["_highlights"]}
    return {"summary": summary, "data": public, "card": {"type": "invoice_check", "data": card}}


class StudyPlanArgs(BaseModel):
    plan_id: int | None = Field(None, description="Optional id of one saved plan; if omitted the most recently updated plan is used")


def t_study_plan(s: Session, a: StudyPlanArgs):
    """READ: return the signed-in user's own server-calculated study funding numbers. The model explains them; it never computes them."""
    if not s.uid:
        return {"summary": "Your study plans are saved to an account. Sign in (or create an account) so I can read your plan.", "data": {"signed_in": False}}
    from . import studystore
    plans = studystore.list_plans(s.uid, s.today)
    if a.plan_id is not None:
        plans = [p for p in plans if p["id"] == a.plan_id]
    if not plans:
        return {"summary": "You have no saved study plan yet. Create one in the 'Study plan' tab, then ask me again.", "data": {"plans": 0}}
    p, r = plans[0], plans[0]["result"]
    c = p["currency"]
    summary = (f"Plan '{p['name']}': total estimated cost {fmt_money(float(r['total_cost']), c)}; confirmed money {fmt_money(float(r['confirmed_money']), c)}; "
               f"confirmed gap {fmt_money(float(r['confirmed_gap']), c)} ({r['coverage_confirmed_pct']}% covered); potential funding "
               f"{fmt_money(float(r['potential_funding']), c)} is NOT confirmed; to close the confirmed gap by the target you would save about "
               f"{fmt_money(float(r['monthly_required']), c)} per month. These are server-calculated estimates from your inputs, not advice.")
    data = {k: r[k] for k in ("currency", "tuition_total", "living_total", "one_time_total", "total_cost", "confirmed_money", "confirmed_gap",
                              "potential_funding", "potential_gap", "coverage_confirmed_pct", "months_to_target", "monthly_required", "on_track")}
    return {"summary": summary, "data": data, "card": {"type": "study_plan", "data": {"name": p["name"], **data}}}


def t_account(s: Session, a: NoArgs):
    bal = ", ".join(fmt_money(v, k) for k, v in s.balances.items())
    return {"summary": f"Sandbox account balances: {bal}. This is a simulated account; no real money is involved.",
            "data": {"balances": dict(s.balances), "transactions": s.transactions},
            "card": {"type": "account", "data": {"balances": dict(s.balances), "transactions": s.transactions}}}


def t_transfer(s: Session, a: TransferArgs):
    res = s.request_transfer(a.quote_id, a.beneficiary_name, a.recipient_country.upper())
    q = s.quotes[a.quote_id]
    if res["status"] == "blocked":
        reasons = " ".join(res["compliance"]["reasons"])
        s.audit.append("compliance_block", {"quote": a.quote_id, "reasons": res["compliance"]["reasons"]})
        return {"summary": f"I can't start this transfer: {reasons}", "data": res,
                "card": {"type": "blocked", "data": {"reasons": res["compliance"]["reasons"]}}}
    s.audit.append("confirmation_requested", {"quote": a.quote_id, "beneficiary": a.beneficiary_name,
                                              "amount": q["send_amount"], "currency": q["send_currency"]})
    card = {"type": "confirmation", "data": {
        "token": res["token"], "provider": q["provider"], "send": q["send_amount"],
        "send_currency": q["send_currency"], "receive": q["receive_amount"],
        "receive_currency": q["receive_currency"], "fee": q["fee"], "beneficiary": a.beneficiary_name,
        "verified_beneficiary": res["verified_beneficiary"], "purpose": q["purpose"],
        "warnings": res["compliance"]["warnings"], "expires_in": res["expires_in"]}}
    summary = (f"Transfer prepared but NOT sent: {fmt_money(q['send_amount'], q['send_currency'])} via {q['provider']} "
               f"so {a.beneficiary_name} receives {fmt_money(q['receive_amount'], q['receive_currency'])}. "
               "Please review and confirm with your PIN. I cannot confirm it for you.")
    return {"summary": summary, "data": {"status": "pending_confirmation"}, "card": card}


@dataclass
class Tool:
    name: str
    tier: Tier
    description: str
    model: type[BaseModel]
    fn: Callable


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_fx_rate", Tier.READ, "Convert an amount between two currencies using the sandbox FX rate.", FxArgs, t_fx),
    Tool("fx_timing", Tier.READ, "30-day FX timing signal (favorable/neutral/unfavorable) for a currency pair.", FxArgs, t_timing),
    Tool("get_account", Tier.READ, "Show sandbox account balances and past transfers.", NoArgs, t_account),
    Tool("compare_remittance_routes", Tier.READ,
         "Compare providers for sending money or paying tuition abroad. basis='receive' means amount is what the "
         "recipient must receive; basis='send' means amount is what the user pays. Returns quote IDs.", CompareArgs, t_compare),
    Tool("get_study_plan", Tier.READ, "Read the signed-in user's saved study funding plan (total cost, confirmed gap, potential funding, monthly saving). "
         "Numbers are calculated by the server; explain them, never recalculate or invent them.", StudyPlanArgs, t_study_plan),
    Tool("build_budget", Tier.SUGGEST, "Build a monthly budget with alerts and savings tips.", BudgetArgs, t_budget),
    Tool("plan_tuition", Tier.SUGGEST, "Plan tuition installments, monthly saving need, FX tranches and reminders.", TuitionArgs, t_tuition),
    Tool("credit_roadmap", Tier.SUGGEST, "Explainable credit-building roadmap for an international student.", CreditArgs, t_credit),
    Tool("check_invoice", Tier.SUGGEST, "Check a pasted tuition invoice for fraud signals and extract payment details.", InvoiceArgs, t_invoice),
    Tool("request_transfer", Tier.EXECUTE,
         "Prepare a transfer from a saved quote. This does NOT move money; the user must confirm with a PIN.", TransferArgs, t_transfer),
]}


def llm_tool_specs() -> list[dict]:
    return [{"name": t.name, "description": f"[Tier {t.tier.name}] {t.description}",
             "input_schema": t.model.model_json_schema()} for t in TOOLS.values()]


def run_tool(session: Session, name: str, raw_args: dict, max_tier: Tier = Tier.EXECUTE) -> dict:
    """Validate, authorise, execute and audit one tool call."""
    session.audit.append("tool_call", {"tool": name, "args": raw_args})
    tool = TOOLS.get(name)
    if not tool:
        res = {"ok": False, "error": f"Unknown tool '{name}'."}
    elif tool.tier > max_tier:
        res = {"ok": False, "error": f"Tool '{name}' needs tier {tool.tier.name}, above the allowed {max_tier.name}."}
    else:
        try:
            args = tool.model(**raw_args)
            out = tool.fn(session, args)
            res = {"ok": True, "tool": name, "tier": tool.tier.name, **out}
        except ValidationError as e:
            msg = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            res = {"ok": False, "error": f"Invalid arguments: {msg}"}
        except (ValueError, fx.FXError, remit.RouteError) as e:
            res = {"ok": False, "error": str(e)}
    session.audit.append("tool_result", {"tool": name, "ok": res["ok"],
                                          "summary": res.get("summary") or res.get("error")})
    return res
