"""Multi-currency student budget builder."""
from . import fx
from .data import NEEDS, WANTS


def build_budget(income: float, income_ccy: str, expenses: dict[str, float],
                 expense_ccy: str, savings_target_pct: float = 20.0) -> dict:
    income_ccy, expense_ccy = fx.norm(income_ccy), fx.norm(expense_ccy)
    if income <= 0:
        raise ValueError("Monthly income must be greater than zero.")
    if not expenses:
        raise ValueError("Please give at least one monthly expense (for example rent 400).")
    lines = {k.lower(): fx.convert(v, expense_ccy, income_ccy) for k, v in expenses.items() if v > 0}
    total = sum(lines.values())
    surplus = income - total
    needs = sum(v for k, v in lines.items() if k in NEEDS or k not in WANTS)
    wants = total - needs
    savings_rate = surplus / income * 100
    alerts, tips = [], []
    rent = lines.get("rent", 0)
    if rent / income > 0.35:
        alerts.append(f"Rent is {rent / income * 100:.0f}% of income (above the 35% guideline).")
    if surplus < 0:
        alerts.append(f"Spending exceeds income by {abs(surplus):,.0f} {income_ccy} per month.")
    elif savings_rate < savings_target_pct:
        alerts.append(f"Savings rate is {savings_rate:.0f}%, below your {savings_target_pct:.0f}% target.")
    gap = savings_target_pct / 100 * income - surplus
    if gap > 0:
        wants_lines = {k: v for k, v in lines.items() if k in WANTS}
        wants_total = sum(wants_lines.values())
        if wants_total > 0:
            for k, v in sorted(wants_lines.items(), key=lambda kv: -kv[1]):
                cut = min(v * 0.5, gap * v / wants_total)
                if cut > 0:
                    tips.append(f"Trim {k} by about {cut:,.0f} {income_ccy} per month.")
        remaining = gap - sum(min(v * 0.5, gap * v / wants_total) for v in wants_lines.values()) if wants_total else gap
        if remaining > 1:
            tips.append(f"Still {remaining:,.0f} {income_ccy} short of the target; review rent or find extra income.")
    emergency = needs * 3
    tips.append(f"Emergency fund goal: about {emergency:,.0f} {income_ccy} (3 months of essentials).")
    return {"income": income, "currency": income_ccy, "expense_currency": expense_ccy,
            "total_expenses": total, "surplus": surplus, "savings_rate": savings_rate,
            "needs": needs, "wants": wants, "target_pct": savings_target_pct,
            "lines": [{"category": k, "amount": v, "share_pct": v / income * 100}
                      for k, v in sorted(lines.items(), key=lambda kv: -kv[1])],
            "alerts": alerts, "tips": tips, "emergency_fund": emergency}
