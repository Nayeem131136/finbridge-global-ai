"""Remittance / tuition-payment route comparison (sandbox providers)."""
from . import fx
from .data import PROVIDERS


class RouteError(ValueError):
    pass


def _fee_usd(p: dict, send_usd: float) -> float:
    return max(p["min_fee_usd"], p["fixed_usd"] + p["pct"] / 100 * send_usd)


def _quote(p: dict, send: float, frm: str, to: str) -> dict:
    send_usd = fx.convert(send, frm, "USD")
    fee = fx.convert(_fee_usd(p, send_usd), "USD", frm)
    mid = fx.rate(frm, to)
    receive = (send - fee) * mid * (1 - p["spread_pct"] / 100)
    cost_frm = fee + (send - fee) * p["spread_pct"] / 100
    return {"provider_id": p["id"], "provider": p["name"], "note": p["note"],
            "send_amount": send, "send_currency": frm, "receive_amount": receive,
            "receive_currency": to, "fee": fee, "spread_pct": p["spread_pct"],
            "total_cost": cost_frm, "total_cost_pct": cost_frm / send * 100,
            "speed_hours": p["speed_hours"], "effective_rate": receive / send}


def _send_for_target(p: dict, target: float, frm: str, to: str) -> float:
    """Amount the sender must pay so the recipient gets exactly `target`."""
    mid = fx.rate(frm, to)
    base = target / (mid * (1 - p["spread_pct"] / 100))
    send = base
    for _ in range(30):
        send_usd = fx.convert(send, frm, "USD")
        fee = fx.convert(_fee_usd(p, send_usd), "USD", frm)
        send = base + fee
    return send


def compare(amount: float, frm: str, to: str, purpose: str = "tuition",
            basis: str = "receive", priority: str = "balanced") -> dict:
    frm, to = fx.norm(frm), fx.norm(to)
    if frm == to:
        raise RouteError("Sender and recipient currency are the same; no conversion is needed.")
    if amount <= 0:
        raise RouteError("Amount must be greater than zero.")
    quotes, excluded = [], []
    for p in PROVIDERS:
        if p["purposes"] and purpose not in p["purposes"]:
            excluded.append({"provider": p["name"], "reason": f"Not available for purpose '{purpose}'."})
            continue
        if p["receive_ccy"] and to not in p["receive_ccy"]:
            excluded.append({"provider": p["name"], "reason": f"Does not deliver {to}."})
            continue
        send = _send_for_target(p, amount, frm, to) if basis == "receive" else amount
        if fx.convert(send, frm, "USD") > p["max_usd"]:
            excluded.append({"provider": p["name"], "reason": f"Above its {p['max_usd']:,} USD limit."})
            continue
        quotes.append(_quote(p, send, frm, to))
    if not quotes:
        raise RouteError("No provider can handle this request. Try a smaller amount or another currency.")
    if priority == "cheapest":
        key = lambda q: (q["total_cost_pct"], q["speed_hours"])
    elif priority == "fastest":
        key = lambda q: (q["speed_hours"], q["total_cost_pct"])
    else:
        key = lambda q: q["total_cost_pct"] + 0.15 * q["speed_hours"] / 24
    quotes.sort(key=key)
    # Comparable cost: cost for the same recipient outcome
    worst = max(quotes, key=lambda q: q["total_cost"])
    best = quotes[0]
    return {"basis": basis, "priority": priority, "purpose": purpose, "quotes": quotes,
            "excluded": excluded, "recommended": best["provider_id"],
            "savings_vs_worst": worst["total_cost"] - best["total_cost"] if len(quotes) > 1 else 0.0,
            "data_note": f"Providers and fees are illustrative sandbox data. FX rate: {fx.source_label()}."}
