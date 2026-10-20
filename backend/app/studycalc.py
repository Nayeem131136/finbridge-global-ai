"""Authoritative study-cost calculations. The ONLY place these formulas live.

Rules (documented in docs/FEATURE_GUIDE.md):
* Decimal arithmetic everywhere; results rounded ROUND_HALF_UP to the currency precision (2 decimals, 0 for JPY).
* One plan = one currency. Nothing here converts currencies.
* Definitions
    total_cost        = tuition_total + living_total + one_time_costs
    confirmed_money   = confirmed_funding + current_savings          (savings counted ONCE, here)
    confirmed_gap     = max(0, total_cost - confirmed_money)
    potential_gap     = max(0, confirmed_gap - potential_funding)    (scenario only, never "confirmed")
    monthly_required  = confirmed_gap / months_to_target             (months from today to target_date; 12 if no date)
* Tuition/living growth is applied per academic year: year n costs base * (1+g)^n; a fractional last year is pro-rated.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

from . import fx

HUNDRED = Decimal("100")
MAX_AMOUNT = Decimal("1000000000")          # 1 billion: reject absurd values
ZERO_DECIMAL = {"JPY"}


class CalcError(ValueError):
    pass


def precision(ccy: str) -> Decimal:
    return Decimal("1") if ccy in ZERO_DECIMAL else Decimal("0.01")


def q(value, ccy: str = "USD") -> Decimal:
    return Decimal(value).quantize(precision(ccy), rounding=ROUND_HALF_UP)


def dec(value, name: str, *, minimum=Decimal("0"), maximum=MAX_AMOUNT, default=None) -> Decimal:
    """Parse a user number into Decimal. Rejects NaN/inf, negatives (unless minimum allows), and absurd sizes."""
    if value is None or value == "":
        if default is None:
            raise CalcError(f"{name} is required.")
        return Decimal(default)
    if isinstance(value, bool):
        raise CalcError(f"{name} must be a number.")
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise CalcError(f"{name} must be a number.")
    if not d.is_finite():
        raise CalcError(f"{name} must be a finite number.")
    if d < minimum:
        raise CalcError(f"{name} cannot be below {minimum}.")
    if d > maximum:
        raise CalcError(f"{name} is too large.")
    return d


def months_between(today: date, target: date | None) -> int:
    if not target:
        return 12
    m = (target.year - today.year) * 12 + (target.month - today.month) + (1 if target.day > today.day else 0)
    return max(1, m)


def _growth_total(base: Decimal, years: Decimal, growth_pct: Decimal) -> Decimal:
    g = Decimal("1") + growth_pct / HUNDRED
    whole = int(years)
    frac = years - whole
    total = sum((base * g ** n for n in range(whole)), Decimal("0"))
    if frac:
        total += base * g ** whole * frac
    return total


def validate_inputs(v: dict) -> dict:
    """Validated Decimal inputs (raises CalcError). Keys: currency, duration_years, annual_tuition, monthly_living,
    one_time_costs, confirmed_funding, potential_funding, current_savings, monthly_savings, tuition_growth_pct,
    living_growth_pct, target_date."""
    try:
        ccy = fx.norm(v.get("currency") or "USD")
    except fx.FXError as e:
        raise CalcError(str(e))
    return {
        "currency": ccy,
        "duration_years": dec(v.get("duration_years"), "Study duration", minimum=Decimal("0.25"), maximum=Decimal("10")),
        "annual_tuition": dec(v.get("annual_tuition"), "Annual tuition"),
        "monthly_living": dec(v.get("monthly_living"), "Monthly living cost"),
        "one_time_costs": dec(v.get("one_time_costs"), "One-time costs", default=0),
        "confirmed_funding": dec(v.get("confirmed_funding"), "Confirmed funding", default=0),
        "potential_funding": dec(v.get("potential_funding"), "Potential funding", default=0),
        "current_savings": dec(v.get("current_savings"), "Current savings", default=0),
        "monthly_savings": dec(v.get("monthly_savings"), "Monthly savings capacity", default=0),
        "tuition_growth_pct": dec(v.get("tuition_growth_pct"), "Tuition growth", minimum=Decimal("-50"), maximum=Decimal("100"), default=0),
        "living_growth_pct": dec(v.get("living_growth_pct"), "Living-cost growth", minimum=Decimal("-50"), maximum=Decimal("100"), default=0),
        "target_date": v.get("target_date"),
    }


def calculate(inp: dict, today: date) -> dict:
    """inp must come from validate_inputs()."""
    c = inp["currency"]
    tuition_total = q(_growth_total(inp["annual_tuition"], inp["duration_years"], inp["tuition_growth_pct"]), c)
    living_total = q(_growth_total(inp["monthly_living"] * 12, inp["duration_years"], inp["living_growth_pct"]), c)
    one_time = q(inp["one_time_costs"], c)
    total = tuition_total + living_total + one_time
    confirmed_money = q(inp["confirmed_funding"] + inp["current_savings"], c)
    confirmed_gap = q(max(Decimal("0"), total - confirmed_money), c)
    potential = q(inp["potential_funding"], c)
    potential_gap = q(max(Decimal("0"), confirmed_gap - potential), c)
    surplus = q(max(Decimal("0"), confirmed_money - total), c)
    pct = lambda a: Decimal("0.00") if total == 0 else min(HUNDRED, (a / total * HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    target = date.fromisoformat(inp["target_date"]) if isinstance(inp.get("target_date"), str) and inp["target_date"] else inp.get("target_date")
    months = months_between(today, target)
    required = q(confirmed_gap / months, c) if confirmed_gap else q(0, c)
    cap = inp["monthly_savings"]
    months_needed = None
    on_track = None
    if confirmed_gap == 0:
        on_track, months_needed = True, 0
    elif cap > 0:
        months_needed = int((confirmed_gap / cap).to_integral_value(rounding=ROUND_CEILING))
        on_track = months_needed <= months
    return {
        "currency": c, "tuition_total": tuition_total, "living_total": living_total, "one_time_total": one_time, "total_cost": total,
        "confirmed_funding": q(inp["confirmed_funding"], c), "current_savings": q(inp["current_savings"], c),
        "confirmed_money": confirmed_money, "potential_funding": potential,
        "confirmed_gap": confirmed_gap, "potential_gap": potential_gap, "surplus": surplus,
        "coverage_confirmed_pct": pct(confirmed_money), "coverage_with_potential_pct": pct(confirmed_money + potential),
        "months_to_target": months, "monthly_required": required, "monthly_capacity": q(cap, c),
        "months_needed_at_capacity": months_needed, "on_track": on_track,
        "rounding": f"ROUND_HALF_UP to {precision(c)} {c}",
    }


def whatif(inp: dict, today: date, *, tuition_change_pct=0, living_change_pct=0, extra_confirmed=0, extra_potential=0, monthly_savings=None) -> dict:
    """Scenario = baseline with its REAL tuition and living values scaled (no fixed tuition/living split),
    extra funding added, and the gap recomputed from scenario total. gap_change = scenario_gap - baseline_gap."""
    t = dec(tuition_change_pct, "Tuition change", minimum=Decimal("-90"), maximum=Decimal("300"), default=0)
    l = dec(living_change_pct, "Living-cost change", minimum=Decimal("-90"), maximum=Decimal("300"), default=0)
    xc = dec(extra_confirmed, "Extra confirmed funding", default=0)
    xp = dec(extra_potential, "Extra potential funding", default=0)
    base = calculate(inp, today)
    s_inp = dict(inp)
    s_inp["annual_tuition"] = inp["annual_tuition"] * (Decimal("1") + t / HUNDRED)
    s_inp["monthly_living"] = inp["monthly_living"] * (Decimal("1") + l / HUNDRED)
    s_inp["confirmed_funding"] = inp["confirmed_funding"] + xc
    s_inp["potential_funding"] = inp["potential_funding"] + xp
    if monthly_savings not in (None, ""):
        s_inp["monthly_savings"] = dec(monthly_savings, "Monthly savings")
    sc = calculate(s_inp, today)
    return {"baseline": base, "scenario": sc,
            "total_change": sc["total_cost"] - base["total_cost"],
            "confirmed_gap_change": sc["confirmed_gap"] - base["confirmed_gap"],
            "potential_gap_change": sc["potential_gap"] - base["potential_gap"]}


def sensitivity(total: Decimal, ccy: str, steps=(-10, -5, 0, 5, 10)) -> list[dict]:
    """How the total changes if the home-currency cost of the plan moves by +/- x% (exchange-rate risk). Educational, not a forecast."""
    return [{"change_pct": s, "adjusted_total": q(total * (Decimal("1") + Decimal(s) / HUNDRED), ccy)} for s in steps]


# ------------------------------------------------------------------ transfer quotes (user-entered)
def quote(*, amount, rate, fee_percent=0, fixed_fee=0, convention="added", send_ccy="BDT", receive_ccy="USD") -> dict:
    """amount = the amount the quote is for, in send currency; rate = receive units per 1 send unit, entered from the provider's own quote.
    'added': fee is charged on top (you pay amount+fee, recipient gets amount*rate).
    'included': you pay `amount`, fee is deducted first (recipient gets (amount-fee)*rate)."""
    try:
        send_ccy, receive_ccy = fx.norm(send_ccy), fx.norm(receive_ccy)
    except fx.FXError as e:
        raise CalcError(str(e))
    if convention not in ("added", "included"):
        raise CalcError("Fee convention must be 'added' or 'included'.")
    a = dec(amount, "Amount")
    if a <= 0:
        raise CalcError("Amount must be greater than zero.")
    r = dec(rate, "Exchange rate")
    if r <= 0:
        raise CalcError("Exchange rate must be greater than zero.")
    fp = dec(fee_percent, "Fee percent", maximum=Decimal("50"), default=0)
    ff = dec(fixed_fee, "Fixed fee", default=0)
    fee = a * fp / HUNDRED + ff
    if convention == "added":
        paid, received = a + fee, a * r
    else:
        if fee >= a:
            raise CalcError("Fee cannot be as large as the amount.")
        paid, received = a, (a - fee) * r
    return {"send_currency": send_ccy, "receive_currency": receive_ccy, "fee": q(fee, send_ccy), "total_paid": q(paid, send_ccy),
            "recipient_gets": q(received, receive_ccy), "effective_rate": (received / paid).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)}
