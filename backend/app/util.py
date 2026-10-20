import re
from datetime import date

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_D1 = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_D2 = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r",?\s+(\d{4})\b", re.I)
_D3 = re.compile(r"\b" + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)


def fmt_money(amount: float, ccy: str) -> str:
    digits = 0 if ccy in ("BDT", "JPY", "INR") else 2
    return f"{amount:,.{digits}f} {ccy}"


def find_dates(text: str) -> list[date]:
    found: list[tuple[int, date]] = []
    for m in _D1.finditer(text):
        try:
            found.append((m.start(), date(int(m[1]), int(m[2]), int(m[3]))))
        except ValueError:
            pass
    for m in _D2.finditer(text):
        try:
            found.append((m.start(), date(int(m[3]), MONTHS[m[2].lower()[:3]], int(m[1]))))
        except ValueError:
            pass
    for m in _D3.finditer(text):
        try:
            found.append((m.start(), date(int(m[3]), MONTHS[m[1].lower()[:3]], int(m[2]))))
        except ValueError:
            pass
    return [d for _, d in sorted(found)]
