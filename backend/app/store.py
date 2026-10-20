"""Per-user persistence: profile, directory, plans, comparisons, records, reminders, wallet, audit.
Every query that touches private data filters by user_id."""
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import budget as budget_mod, fx, remit, tuition as tuition_mod
from . import db
from .data import DEFAULT_BALANCES
from .security import AuditLog


def _d(row):
    return dict(row) if row else None


# ----------------------------------------------------------------- profile / directory
PROFILE_FIELDS = ["home_country", "study_country", "language", "currency", "timezone", "study_level", "university_id",
                  "university_other", "program", "monthly_income", "monthly_budget", "tuition_date",
                  "remind_tuition", "remind_budget", "remind_savings"]
CLEARABLE = ["home_country", "study_country", "study_level", "university_id", "university_other", "program",
             "monthly_income", "monthly_budget", "tuition_date"]


def get_profile(uid: int) -> dict:
    row = db.q1("""SELECT p.*, u.name AS uni_name, u.country AS uni_country, u.city AS uni_city, u.source AS uni_source
                   FROM profiles p LEFT JOIN universities u ON u.id = p.university_id WHERE p.user_id = ?""", (uid,))
    p = _d(row) or {}
    for k in ("remind_tuition", "remind_budget", "remind_savings"):
        p[k] = bool(p.get(k, 1))
    return p


def save_profile(uid: int, values: dict) -> None:
    cols = [k for k in values if k in PROFILE_FIELDS]
    if not cols:
        return
    sets = ", ".join(f"{k} = ?" for k in cols)
    db.run(f"UPDATE profiles SET {sets}, updated_at = datetime('now') WHERE user_id = ?",
           tuple((int(values[k]) if isinstance(values[k], bool) else values[k]) for k in cols) + (uid,))


def clear_profile(uid: int) -> None:
    sets = ", ".join(f"{k} = NULL" for k in CLEARABLE)
    db.run(f"UPDATE profiles SET {sets}, updated_at = datetime('now') WHERE user_id = ?", (uid,))


def search_universities(q: str = "", country: str = "", limit: int = 30) -> list[dict]:
    sql, args = "SELECT id, name, country, city, source FROM universities WHERE 1=1", []
    if q:
        sql += " AND (name LIKE ? ESCAPE '\\' OR city LIKE ? ESCAPE '\\')"
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        args += [like, like]
    if country:
        sql += " AND country = ?"; args.append(country.upper())
    return [dict(r) for r in db.q(sql + " ORDER BY country, name LIMIT ?", tuple(args) + (limit,))]


def university_countries() -> list[str]:
    return [r["country"] for r in db.q("SELECT DISTINCT country FROM universities ORDER BY country")]


def university_exists(uni_id: int) -> bool:
    return db.q1("SELECT 1 FROM universities WHERE id = ?", (uni_id,)) is not None


# ----------------------------------------------------------------- budgets
def _budget_view(r) -> dict:
    d = dict(r)
    d["expenses"] = json.loads(d["expenses"])
    d["result"] = budget_mod.build_budget(d["income"], d["currency"], d["expenses"], d["currency"], d["target_pct"])
    return d


def list_budgets(uid: int) -> list[dict]:
    return [_budget_view(r) for r in db.q("SELECT * FROM budgets WHERE user_id = ? ORDER BY updated_at DESC, id DESC", (uid,))]


def get_budget(uid: int, bid: int):
    r = db.q1("SELECT * FROM budgets WHERE id = ? AND user_id = ?", (bid, uid))
    return _budget_view(r) if r else None


def save_budget(uid: int, name: str, income: float, ccy: str, expenses: dict, target_pct: float, bid: int | None = None):
    fx.norm(ccy)
    if bid is None:
        cur = db.run("INSERT INTO budgets(user_id, name, income, currency, expenses, target_pct) VALUES (?,?,?,?,?,?)",
                     (uid, name, income, ccy, json.dumps(expenses), target_pct))
        return get_budget(uid, cur.lastrowid)
    cur = db.run("UPDATE budgets SET name=?, income=?, currency=?, expenses=?, target_pct=?, updated_at=datetime('now') WHERE id=? AND user_id=?",
                 (name, income, ccy, json.dumps(expenses), target_pct, bid, uid))
    return get_budget(uid, bid) if cur.rowcount else None


def delete_budget(uid: int, bid: int) -> bool:
    return db.run("DELETE FROM budgets WHERE id = ? AND user_id = ?", (bid, uid)).rowcount > 0


# ----------------------------------------------------------------- tuition plans
def today_for(tz: str | None) -> date:
    try:
        return datetime.now(ZoneInfo(tz or "Asia/Dhaka")).date()
    except Exception:
        return date.today()


def _tuition_view(r, today: date) -> dict:
    d = dict(r)
    d["due_dates"] = json.loads(d["due_dates"])
    dues = sorted(date.fromisoformat(x) for x in d["due_dates"])
    upcoming = [x for x in dues if x >= today]
    mid = fx.rate(d["home_currency"], d["currency"])
    total_home = d["total"] / mid
    d["total_home"] = total_home
    d["progress_pct"] = min(100.0, d["saved"] / total_home * 100) if total_home else 0.0
    d["status"] = "upcoming" if upcoming else "past_due_dates"
    d["next_due"] = upcoming[0].isoformat() if upcoming else None
    d["days_to_next_due"] = (upcoming[0] - today).days if upcoming else None
    d["plan"] = None
    d["shortfall_monthly"] = None
    if upcoming:
        share = d["total"] * len(upcoming) / len(dues)           # only the installments still ahead
        d["plan"] = tuition_mod.plan(share, d["currency"], upcoming, today, d["saved"], d["monthly_saving"], d["home_currency"])
        d["shortfall_monthly"] = d["plan"]["gap"]
    d["note"] = ("Estimates use your inputs and the current exchange-rate assumption "
                 f"({fx.source_label()}). They are not a payment instruction.")
    return d


def list_tuition(uid: int, today: date) -> list[dict]:
    return [_tuition_view(r, today) for r in db.q("SELECT * FROM tuition_plans WHERE user_id = ? ORDER BY updated_at DESC, id DESC", (uid,))]


def get_tuition(uid: int, pid: int, today: date):
    r = db.q1("SELECT * FROM tuition_plans WHERE id = ? AND user_id = ?", (pid, uid))
    return _tuition_view(r, today) if r else None


def save_tuition(uid: int, today: date, v: dict, pid: int | None = None):
    fx.norm(v["currency"]); fx.norm(v["home_currency"])
    args = (v["name"], v["total"], v["currency"], json.dumps(sorted(v["due_dates"])), v["home_currency"], v["saved"], v["monthly_saving"])
    if pid is None:
        cur = db.run("INSERT INTO tuition_plans(user_id, name, total, currency, due_dates, home_currency, saved, monthly_saving) VALUES (?,?,?,?,?,?,?,?)", (uid,) + args)
        return get_tuition(uid, cur.lastrowid, today)
    cur = db.run("UPDATE tuition_plans SET name=?, total=?, currency=?, due_dates=?, home_currency=?, saved=?, monthly_saving=?, updated_at=datetime('now') WHERE id=? AND user_id=?", args + (pid, uid))
    return get_tuition(uid, pid, today) if cur.rowcount else None


def delete_tuition(uid: int, pid: int) -> bool:
    return db.run("DELETE FROM tuition_plans WHERE id = ? AND user_id = ?", (pid, uid)).rowcount > 0


# ----------------------------------------------------------------- comparisons
def save_comparison(uid: int, amount: float, frm: str, to: str, purpose: str, basis: str, label: str | None) -> dict:
    res = remit.compare(amount, frm, to, purpose, basis)        # recomputed on the server; the client snapshot is never trusted
    best = res["quotes"][0]
    label = (label or f"{amount:,.0f} {to} via {best['provider'].split(' (')[0]}")[:80]
    cur = db.run("INSERT INTO comparisons(user_id, label, amount, from_ccy, to_ccy, purpose, basis, best, snapshot, fx_source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (uid, label, amount, res["quotes"][0]["send_currency"], res["quotes"][0]["receive_currency"], purpose, basis,
                  best["provider"], json.dumps({"quotes": res["quotes"], "excluded": res["excluded"], "savings_vs_worst": res["savings_vs_worst"]}), fx.SOURCE))
    return get_comparison(uid, cur.lastrowid)


def _cmp_view(r) -> dict:
    d = dict(r)
    d["snapshot"] = json.loads(d["snapshot"])
    d["note"] = "Saved snapshot of illustrative sandbox quotes. Not a live offer."
    return d


def list_comparisons(uid: int) -> list[dict]:
    return [_cmp_view(r) for r in db.q("SELECT * FROM comparisons WHERE user_id = ? ORDER BY id DESC LIMIT 50", (uid,))]


def get_comparison(uid: int, cid: int):
    r = db.q1("SELECT * FROM comparisons WHERE id = ? AND user_id = ?", (cid, uid))
    return _cmp_view(r) if r else None


def delete_comparison(uid: int, cid: int) -> bool:
    return db.run("DELETE FROM comparisons WHERE id = ? AND user_id = ?", (cid, uid)).rowcount > 0


# ----------------------------------------------------------------- records / activity
def list_records(uid: int, limit: int = 30) -> list[dict]:
    out = []
    for r in db.q("SELECT ref, kind, detail, created_at FROM sandbox_records WHERE user_id = ? ORDER BY id DESC LIMIT ?", (uid, limit)):
        out.append({"ref": r["ref"], "kind": r["kind"], "created_at": r["created_at"], **json.loads(r["detail"])})
    return out


# ----------------------------------------------------------------- reminders
def refresh_reminders(uid: int) -> None:
    """Create in-app reminders (no email/push is sent). dedupe_key makes this idempotent."""
    prof = get_profile(uid)
    today = today_for(prof.get("timezone"))
    new = []                                   # (kind, key, message, due_on)
    if prof.get("remind_tuition"):
        for p in list_tuition(uid, today):
            for ds in p["due_dates"]:
                due = date.fromisoformat(ds)
                for window in (14, 7, 3):
                    if 0 <= (due - today).days <= window:
                        new.append(("tuition_due", f"tuition:{p['id']}:{ds}:{window}",
                                    f"Tuition '{p['name']}' has an installment due on {ds} ({(due - today).days} day(s) left). Verify payment details with your university's official finance office.", ds))
                        break
    if prof.get("remind_savings"):
        for p in list_tuition(uid, today):
            for m in (100, 75, 50, 25):
                if p["progress_pct"] >= m:
                    new.append(("savings_milestone", f"savings:{p['id']}:{m}", f"Savings milestone: '{p['name']}' has reached {m}% of its target (based on the savings you entered).", None))
                    break
    if prof.get("remind_budget"):
        for b in list_budgets(uid):
            upd = datetime.fromisoformat(b["updated_at"]).date()
            if (today - upd).days >= 30:
                new.append(("budget_review", f"budget:{b['id']}:{today.strftime('%Y-%m')}", f"Time to review your budget '{b['name']}' (last updated {upd.isoformat()}).", None))
    with db.tx() as c:
        for kind, key, msg, due in new:
            c.execute("INSERT OR IGNORE INTO notifications(user_id, kind, dedupe_key, message, due_on) VALUES (?,?,?,?,?)", (uid, kind, key, msg, due))


def list_notifications(uid: int, include_read: bool = False) -> list[dict]:
    sql = "SELECT id, kind, message, due_on, read, created_at FROM notifications WHERE user_id = ?" + ("" if include_read else " AND read = 0") + " ORDER BY id DESC LIMIT 50"
    return [dict(r) | {"read": bool(r["read"])} for r in db.q(sql, (uid,))]


def mark_notification(uid: int, nid: int) -> bool:
    return db.run("UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?", (nid, uid)).rowcount > 0


# ----------------------------------------------------------------- wallet + audit persistence
def load_session_state(uid: int, session) -> None:
    rows = db.q("SELECT currency, amount FROM wallet_balances WHERE user_id = ?", (uid,))
    if not rows:
        with db.tx() as c:
            for ccy, amt in DEFAULT_BALANCES.items():
                c.execute("INSERT OR IGNORE INTO wallet_balances(user_id, currency, amount) VALUES (?,?,?)", (uid, ccy, amt))
        rows = db.q("SELECT currency, amount FROM wallet_balances WHERE user_id = ?", (uid,))
    session.balances = {r["currency"]: r["amount"] for r in rows}
    entries = [json.loads(r["body"]) for r in db.q("SELECT body FROM audit_events WHERE user_id = ? ORDER BY seq", (uid,))]
    session.audit = AuditLog()
    session.audit.entries = entries
    session.persist_state["audit"] = len(entries)
    for r in db.q("SELECT detail FROM sandbox_records WHERE user_id = ? AND kind = 'transfer' AND date(created_at) = date('now')", (uid,)):
        session.transactions.append({"usd": json.loads(r["detail"]).get("usd", 0.0)})
    session.persist_state["tx"] = len(session.transactions)


def persist_session(uid: int, s) -> None:
    st = s.persist_state
    with db.tx() as c:
        for ccy, amt in s.balances.items():
            c.execute("INSERT INTO wallet_balances(user_id, currency, amount) VALUES (?,?,?) ON CONFLICT(user_id, currency) DO UPDATE SET amount = excluded.amount", (uid, ccy, amt))
        for t in s.transactions[st["tx"]:]:
            if "ref" in t:
                c.execute("INSERT OR IGNORE INTO sandbox_records(user_id, ref, kind, detail) VALUES (?,?,?,?)", (uid, t["ref"], "transfer", json.dumps(t)))
        st["tx"] = len(s.transactions)
        for e in s.ledger[st["ledger"]:]:
            c.execute("INSERT OR IGNORE INTO sandbox_records(user_id, ref, kind, detail) VALUES (?,?,?,?)", (uid, e["ref"], e["type"], json.dumps(e)))
        st["ledger"] = len(s.ledger)
        for e in s.audit.entries[st["audit"]:]:
            c.execute("INSERT OR REPLACE INTO audit_events(user_id, seq, body) VALUES (?,?,?)", (uid, e["seq"], json.dumps(e, default=str)))
        st["audit"] = len(s.audit.entries)


def delete_user(uid: int) -> None:
    db.run("DELETE FROM users WHERE id = ?", (uid,))          # cascades to every private table
