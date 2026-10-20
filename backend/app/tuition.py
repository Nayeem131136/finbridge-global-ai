"""Tuition payment planner with FX-tranche suggestion and reminders."""
import math
from datetime import date, timedelta

from . import fx


def plan(total: float, ccy: str, due_dates: list[date], today: date, saved: float = 0.0,
         monthly_capacity: float | None = None, home_ccy: str = "BDT") -> dict:
    ccy, home_ccy = fx.norm(ccy), fx.norm(home_ccy)
    if total <= 0:
        raise ValueError("Tuition total must be greater than zero.")
    if not due_dates:
        raise ValueError("I need at least one due date (for example 15 Dec 2026).")
    dues = sorted(due_dates)
    if dues[0] < today:
        raise ValueError(f"The first due date ({dues[0].isoformat()}) is already in the past.")
    per = total / len(dues)
    schedule, required_monthly = [], 0.0
    saved_home = saved  # `saved` is in home currency
    mid = fx.rate(home_ccy, ccy)
    for i, d in enumerate(dues):
        months = max(0.5, (d - today).days / 30.4)
        cum_need_home = per * (i + 1) / mid
        need_more = max(0.0, cum_need_home - saved_home)
        required_monthly = max(required_monthly, need_more / months)
        schedule.append({"due": d.isoformat(), "amount": per, "currency": ccy,
                         "amount_home": per / mid, "home_currency": home_ccy,
                         "remind_on": [(d - timedelta(days=14)).isoformat(), (d - timedelta(days=3)).isoformat()],
                         "days_left": (d - today).days})
    feasible = None if monthly_capacity is None else monthly_capacity >= required_monthly
    gap = None if monthly_capacity is None else max(0.0, required_monthly - monthly_capacity)
    first_months = max(1, int((dues[0] - today).days / 30.4))
    tranches = max(1, min(3, first_months))
    first_home = schedule[0]["amount_home"]
    t = fx.timing(home_ccy, ccy)
    tranche_plan = [{"step": i + 1, "convert_home": first_home / tranches,
                     "when": (today + timedelta(days=int((dues[0] - today).days * (i + 1) / (tranches + 1)))).isoformat()}
                    for i in range(tranches)]
    return {"total": total, "currency": ccy, "home_currency": home_ccy, "installments": len(dues),
            "schedule": schedule, "saved": saved, "required_monthly": required_monthly,
            "monthly_capacity": monthly_capacity, "feasible": feasible, "gap": gap,
            "tranche_plan": tranche_plan, "fx_signal": t["signal"], "fx_advice": t["advice"],
            "current_rate": mid}
