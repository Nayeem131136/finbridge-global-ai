"""Persistence for study plans, user-entered quotes and checklists. Every query filters by user_id."""
from datetime import date, datetime, timezone
from decimal import Decimal

from . import db, fx, studycalc as sc

NUM_FIELDS = ["duration_years", "annual_tuition", "monthly_living", "one_time_costs", "confirmed_funding", "potential_funding",
              "current_savings", "monthly_savings", "tuition_growth_pct", "living_growth_pct"]
TEXT_FIELDS = ["name", "destination_country", "university_other", "program", "notes", "target_date"]
DEFAULT_CHECKLIST = [
    "Check your passport is valid for the whole stay",
    "Confirm the offer letter and tuition amount on the university's official website",
    "Prepare proof of funds required by the visa authority",
    "Apply for the student visa through the official government portal",
    "Arrange health insurance",
    "Verify payment details with the university finance office before paying (never trust emailed bank-detail changes)",
    "Plan arrival accommodation and first-month budget",
]


def _view(row, today: date) -> dict:
    d = dict(row)
    inp = sc.validate_inputs({**{k: d[k] for k in NUM_FIELDS}, "currency": d["currency"], "target_date": d["target_date"]})
    res = sc.calculate(inp, today)
    d["result"] = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in res.items()}
    d["total_cost_value"] = res["total_cost"]                    # Decimal, stripped before JSON by the API layer
    d["uni_name"] = db.q1("SELECT name FROM universities WHERE id = ?", (d["university_id"],))["name"] if d["university_id"] else None
    return d


def public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "total_cost_value"}


def list_plans(uid: int, today: date) -> list[dict]:
    return [public(_view(r, today)) for r in db.q("SELECT * FROM study_plans WHERE user_id = ? ORDER BY updated_at DESC, id DESC", (uid,))]


def get_plan(uid: int, pid: int, today: date):
    r = db.q1("SELECT * FROM study_plans WHERE id = ? AND user_id = ?", (pid, uid))
    return public(_view(r, today)) if r else None


def raw_inputs(plan: dict) -> dict:
    return sc.validate_inputs({**{k: plan[k] for k in NUM_FIELDS}, "currency": plan["currency"], "target_date": plan["target_date"]})


class LimitError(ValueError):
    pass


MAX_PLANS, MAX_QUOTES, MAX_CHECKS = 30, 20, 100


def _count(sql, args):
    return db.q1(sql, args)["n"]


def save_plan(uid: int, v: dict, today: date, pid: int | None = None):
    if pid is None and _count("SELECT COUNT(*) AS n FROM study_plans WHERE user_id = ?", (uid,)) >= MAX_PLANS:
        raise LimitError(f"You can keep up to {MAX_PLANS} plans. Delete one first.")
    cols = {k: str(v[k]) for k in NUM_FIELDS}
    cols.update({k: v.get(k) for k in TEXT_FIELDS})
    cols["currency"] = v["currency"]
    cols["university_id"] = v.get("university_id")
    if pid is None:
        names = ",".join(cols)
        cur = db.run(f"INSERT INTO study_plans(user_id,{names}) VALUES (?,{','.join('?' * len(cols))})", (uid, *cols.values()))
        pid = cur.lastrowid
        with db.tx() as c:
            for t in DEFAULT_CHECKLIST:
                c.execute("INSERT INTO checklist_items(user_id, plan_id, title) VALUES (?,?,?)", (uid, pid, t))
    else:
        sets = ",".join(f"{k} = ?" for k in cols)
        if not db.run(f"UPDATE study_plans SET {sets}, updated_at = datetime('now') WHERE id = ? AND user_id = ?", (*cols.values(), pid, uid)).rowcount:
            return None
    return get_plan(uid, pid, today)


def delete_plan(uid: int, pid: int) -> bool:
    return db.run("DELETE FROM study_plans WHERE id = ? AND user_id = ?", (pid, uid)).rowcount > 0


def duplicate_plan(uid: int, pid: int, today: date):
    r = db.q1("SELECT * FROM study_plans WHERE id = ? AND user_id = ?", (pid, uid))
    if not r:
        return None
    d = dict(r)
    v = {k: d[k] for k in NUM_FIELDS + TEXT_FIELDS + ["currency", "university_id"]}
    v["name"] = (d["name"] + " (copy)")[:80]
    for k in NUM_FIELDS:
        v[k] = Decimal(v[k])
    return save_plan(uid, v, today)


# ---------------------------------------------------------------- quotes (user-entered)
def add_quote(uid: int, pid: int, v: dict):
    if not db.q1("SELECT 1 FROM study_plans WHERE id = ? AND user_id = ?", (pid, uid)):
        return None
    if _count("SELECT COUNT(*) AS n FROM plan_quotes WHERE plan_id = ?", (pid,)) >= MAX_QUOTES:
        raise LimitError(f"Up to {MAX_QUOTES} quotes per plan.")
    cur = db.run("""INSERT INTO plan_quotes(user_id, plan_id, provider, send_currency, receive_currency, amount, rate, fee_percent, fixed_fee, convention, delivery_days, as_of)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (uid, pid, v["provider"], v["send_currency"], v["receive_currency"], str(v["amount"]), str(v["rate"]),
                                                          str(v["fee_percent"]), str(v["fixed_fee"]), v["convention"], v.get("delivery_days"), v.get("as_of")))
    return cur.lastrowid


def list_quotes(uid: int, pid: int) -> list[dict]:
    out = []
    for r in db.q("SELECT * FROM plan_quotes WHERE plan_id = ? AND user_id = ? ORDER BY id", (pid, uid)):
        d = dict(r)
        res = sc.quote(amount=d["amount"], rate=d["rate"], fee_percent=d["fee_percent"], fixed_fee=d["fixed_fee"], convention=d["convention"],
                       send_ccy=d["send_currency"], receive_ccy=d["receive_currency"])
        d["result"] = {k: str(v) for k, v in res.items()}
        d["_eff"] = res["effective_rate"]
        out.append(d)
    comparable = [d for d in out if (d["send_currency"], d["receive_currency"]) == ((out[0]["send_currency"], out[0]["receive_currency"]) if out else None)]
    best = max(comparable, key=lambda d: d["_eff"])["id"] if len(comparable) > 1 else None
    for d in out:
        d["best"] = d["id"] == best
        d.pop("_eff")
        d["source_label"] = "Entered by you. Verify with the provider before paying."
        seen = d.get("as_of") or (d["created_at"] or "")[:16].replace(" ", "T")
        d["seen_at"] = seen
        d["seen_is_entered"] = bool(d.get("as_of"))          # False = we only know when you saved it
        try:
            age = (datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(seen)).total_seconds() / 3600
        except ValueError:
            age = None
        d["age_hours"] = None if age is None else round(max(age, 0), 1)
        d["stale"] = age is None or age > 24                # rates move; re-check anything older than a day
        m = fx.market_info(d["send_currency"], d["receive_currency"])
        d["market"] = m
        mr = Decimal(str(m["rate"]))
        d["vs_market_pct"] = str(((Decimal(d["rate"]) - mr) / mr * 100).quantize(Decimal("0.01")))   # negative = worse than market
    return out


def delete_quote(uid: int, qid: int) -> bool:
    return db.run("DELETE FROM plan_quotes WHERE id = ? AND user_id = ?", (qid, uid)).rowcount > 0


# ---------------------------------------------------------------- checklist
def list_checklist(uid: int, pid: int | None = None) -> list[dict]:
    if pid is None:
        rows = db.q("SELECT * FROM checklist_items WHERE user_id = ? ORDER BY done, id", (uid,))
    else:
        rows = db.q("SELECT * FROM checklist_items WHERE user_id = ? AND plan_id = ? ORDER BY done, id", (uid, pid))
    return [dict(r) | {"done": bool(r["done"])} for r in rows]


def add_check(uid: int, pid: int | None, title: str, due: str | None):
    if pid is not None and not db.q1("SELECT 1 FROM study_plans WHERE id = ? AND user_id = ?", (pid, uid)):
        return None
    if _count("SELECT COUNT(*) AS n FROM checklist_items WHERE user_id = ?", (uid,)) >= MAX_CHECKS:
        raise LimitError(f"Up to {MAX_CHECKS} checklist items.")
    return db.run("INSERT INTO checklist_items(user_id, plan_id, title, due_date) VALUES (?,?,?,?)", (uid, pid, title, due)).lastrowid


def update_check(uid: int, cid: int, done: bool | None, title: str | None, due: str | None) -> bool:
    row = db.q1("SELECT * FROM checklist_items WHERE id = ? AND user_id = ?", (cid, uid))
    if not row:
        return False
    db.run("UPDATE checklist_items SET done = ?, title = ?, due_date = ? WHERE id = ? AND user_id = ?",
           (int(row["done"] if done is None else done), title or row["title"], due if due is not None else row["due_date"], cid, uid))
    return True


def delete_check(uid: int, cid: int) -> bool:
    return db.run("DELETE FROM checklist_items WHERE id = ? AND user_id = ?", (cid, uid)).rowcount > 0


def scholarships(country: str = "", q: str = "") -> list[dict]:
    sql, args = "SELECT * FROM scholarships WHERE 1=1", []
    if country:
        sql += " AND (destination = ? OR destination = 'Multiple')"; args.append(country)
    if q:
        sql += " AND name LIKE ? ESCAPE '\\'"; args.append("%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%")
    return [dict(r) for r in db.q(sql + " ORDER BY name", tuple(args))]
