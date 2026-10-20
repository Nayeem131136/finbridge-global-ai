"""Tuition invoice checker: extracts payment details and flags fraud signals.

The invoice text is untrusted data. It is parsed with regexes only and is
never executed or passed to the agent as instructions.
"""
import re

from .data import BENEFICIARIES, CURRENCY_ALIASES, SYMBOLS
from .security import injection_spans, scan_injection
from .util import find_dates

_CUR = "|".join(sorted(set(CURRENCY_ALIASES) , key=len, reverse=True))
_AMT_CODE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(" + _CUR + r")\b", re.I)
_AMT_PRE = re.compile(r"\b(" + _CUR + r")\s*(\d[\d,]*(?:\.\d+)?)", re.I)
_AMT_SYM = re.compile(r"([$£€৳])\s?(\d[\d,]*(?:\.\d+)?)")
_BENEF = re.compile(r"beneficiary(?: name)?\s*[:\-]\s*([^\n\r;]+?)(?=\.\s|\.$|;|\n|\r|\s+account\b|\s+iban\b|\s+amount\b|\s+due\b|$)", re.I)
_ACCT = re.compile(r"(?i:iban|account(?: no\.?| number)?)\s*[:\-]\s*([A-Z0-9][A-Z0-9 ]{7,40}[A-Z0-9])")
_PRESSURE = re.compile(r"\b(urgent(ly)?|immediately|within 24 hours|last warning|final notice|"
                       r"or (you|your).{0,30}(deport|cancel|expel)|gift card|crypto|bitcoin)\b", re.I)
_CHANGED = re.compile(r"\b(new|changed|updated)\s+(bank|account|payment)\s+(details|instructions|account)|"
                      r"\b(bank|account|payment)\s+(details|instructions)\s+(have\s+|has\s+)?(been\s+)?(changed|updated)", re.I)
_CHAT = re.compile(r"\b(whatsapp|telegram|wechat)\b", re.I)


def _amount(text: str):
    m = _AMT_CODE.search(text)
    if m:
        return float(m[1].replace(",", "")), CURRENCY_ALIASES[m[2].lower()]
    m = _AMT_PRE.search(text)
    if m:
        return float(m[2].replace(",", "")), CURRENCY_ALIASES[m[1].lower()]
    m = _AMT_SYM.search(text)
    if m:
        return float(m[2].replace(",", "")), SYMBOLS[m[1]]
    return None, None


def _norm_acct(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def highlights(text: str, saved_acct: str | None, flagged_benef: bool) -> list[dict]:
    """Character ranges of the invoice text worth a closer look (for the annotated view)."""
    spans = []
    for rx, level, label in ((_CHANGED, "high", "Changed bank details"), (_PRESSURE, "medium", "Pressure language"),
                             (_CHAT, "medium", "Chat-app contact")):
        spans += [{"start": m.start(), "end": m.end(), "level": level, "label": label} for m in rx.finditer(text)]
    spans += [{"start": a, "end": b, "level": "high", "label": "Instruction aimed at an AI (ignored)"} for a, b in injection_spans(text)]
    m = _BENEF.search(text)
    if m and flagged_benef:
        spans.append({"start": m.start(1), "end": m.end(1), "level": "high", "label": "Beneficiary not verified"})
    m = _ACCT.search(text)
    if m and saved_acct and _norm_acct(m.group(1)) != _norm_acct(saved_acct):
        spans.append({"start": m.start(1), "end": m.end(1), "level": "high", "label": "Account differs from verified one"})
    spans.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    out, last = [], 0
    for sp in spans:                      # drop overlaps so the view stays readable
        if sp["start"] >= last:
            out.append(sp); last = sp["end"]
    return out


def check(text: str) -> dict:
    amount, ccy = _amount(text)
    dates = find_dates(text)
    benef = (_BENEF.search(text).group(1).strip() if _BENEF.search(text) else None)
    acct = (_ACCT.search(text).group(1).strip() if _ACCT.search(text) else None)
    flags = []
    saved = BENEFICIARIES.get(benef) if benef else None
    if benef and not saved:
        flags.append({"level": "high", "msg": f"Beneficiary '{benef}' is not in your verified list. "
                      "Confirm with the university finance office using a phone number from their official website."})
    if saved and acct and _norm_acct(acct) != _norm_acct(saved["account"]):
        flags.append({"level": "high", "msg": "Account number does not match the verified account on file for this beneficiary. "
                      "This is a common invoice-fraud pattern. Do not pay."})
    if _CHANGED.search(text):
        flags.append({"level": "high", "msg": "The invoice announces new or changed bank details. Verify by phone with the university before paying."})
    if _PRESSURE.search(text):
        flags.append({"level": "medium", "msg": "Pressure or threat language found. Legitimate universities rarely demand immediate payment by unusual methods."})
    if _CHAT.search(text):
        flags.append({"level": "medium", "msg": "Payment contact is via a chat app. Use official university channels only."})
    inj = scan_injection(text)
    if inj:
        flags.append({"level": "high", "msg": "The document contains text that tries to give instructions to an AI assistant. It was ignored and treated as data."})
    if amount is None:
        flags.append({"level": "low", "msg": "No amount found; please check the invoice manually."})
    if not dates:
        flags.append({"level": "low", "msg": "No due date found."})
    high = any(f["level"] == "high" for f in flags)
    verdict = "do_not_pay" if high else ("review" if flags else "looks_consistent")
    return {"amount": amount, "currency": ccy, "due_date": dates[0].isoformat() if dates else None,
            "beneficiary": benef, "account_masked": (lambda a: a[:4] + " **** " + a[-4:])(_norm_acct(acct)) if acct else None,
            "verified_beneficiary": bool(saved), "flags": flags, "verdict": verdict,
            "injection_detected": bool(inj),
            "_text": text[:3000], "_highlights": [h for h in highlights(text, saved["account"] if saved else None, bool(benef and not saved)) if h["end"] <= 3000]}
