"""FX helpers: rates, conversion, 30-day history and a timing signal.

The history is a deterministic synthetic series (seeded by the pair) so that
demos and tests are reproducible. The timing signal is educational, not a
prediction.
"""
import random
from datetime import datetime, timezone
import zlib

import httpx

from .data import USD_RATES

SOURCE = "sandbox"          # "sandbox" or "live"
UPDATED = None              # ISO time of the last successful live refresh
LIVE_URL = "https://open.er-api.com/v6/latest/USD"   # free, no key; attribution required by the provider


class FXError(ValueError):
    pass


def norm(ccy: str) -> str:
    c = (ccy or "").strip().upper()
    if c not in USD_RATES:
        raise FXError(f"Unsupported currency '{ccy}'. Supported: {', '.join(sorted(USD_RATES))}")
    return c


def rate(frm: str, to: str) -> float:
    return USD_RATES[norm(to)] / USD_RATES[norm(frm)]


def convert(amount: float, frm: str, to: str) -> float:
    return amount * rate(frm, to)


def history(frm: str, to: str, days: int = 30) -> list[float]:
    r0 = rate(frm, to)
    rng = random.Random(zlib.crc32(f"{norm(frm)}{norm(to)}".encode()))
    vals = [r0]
    for _ in range(days - 1):
        vals.append(vals[-1] * (1 + rng.gauss(0, 0.004)))
    vals.reverse()          # oldest first, newest == current rate
    return vals


def timing(frm: str, to: str) -> dict:
    h = history(frm, to)
    cur = h[-1]
    avg = sum(h) / len(h)
    pct_rank = round(sum(1 for v in h if v <= cur) / len(h) * 100)
    vs_avg = (cur / avg - 1) * 100
    if pct_rank >= 70:
        signal, advice = "favorable", "Today's rate is better than most of the last 30 days. Converting a larger share now is reasonable."
    elif pct_rank <= 30:
        signal, advice = "unfavorable", "Today's rate is weaker than most of the last 30 days. Consider splitting the conversion into 2-3 tranches."
    else:
        signal, advice = "neutral", "Today's rate is near its 30-day middle. A split into 2 tranches reduces timing risk."
    return {"from": norm(frm), "to": norm(to), "current": cur, "avg30": avg, "min30": min(h),
            "max30": max(h), "percentile": pct_rank, "vs_avg_pct": vs_avg, "signal": signal,
            "advice": advice, "series": h,
            "disclaimer": "Educational signal from a 30-day window. It is not a prediction or financial advice."}


def source_label() -> str:
    return ("live mid-market rate from open.er-api.com" if SOURCE == "live"
            else "illustrative sandbox rate")


def refresh_live(http=None, url: str = LIVE_URL) -> bool:
    """Replace sandbox rates with live ones. Never raises; keeps sandbox rates on any failure."""
    global SOURCE, UPDATED
    try:
        r = (http or httpx).get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        rates = data["rates"]
        if data.get("result") not in (None, "success"):
            return False
        updated = {c: float(rates[c]) for c in USD_RATES if c in rates and float(rates[c]) > 0}
        if "USD" not in updated or len(updated) < len(USD_RATES) - 2:
            return False        # incomplete answer; do not half-update
        USD_RATES.update(updated)
        SOURCE = "live"
        UPDATED = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return True
    except Exception:
        return False


def market_info(frm: str, to: str) -> dict:
    """Reference mid-market rate with an honest label of where it came from."""
    live = SOURCE == "live"
    return {"from": frm, "to": to, "rate": round(rate(frm, to), 8), "source": "live" if live else "sample",
            "updated": UPDATED if live else None,
            "label": ("Live mid-market rate (open.er-api.com). A reference, not a bank price." if live
                      else "Fixed sample rate used when the live feed is unavailable. A reference only, not a bank price.")}
