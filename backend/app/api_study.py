"""Study planning API (ported from the Django project): plans, what-if, user-entered quotes, checklist, scholarships, PDF report."""
import io
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from . import db, fx, studycalc as sc, studystore as ss, userctx
from .studystore import LimitError
from .api_user import _nf, _text, _today
from .userctx import require_user

router = APIRouter(prefix="/api")
Num = str | int | float | None


class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    currency: str = "USD"
    destination_country: str | None = None
    university_id: int | None = None
    university_other: str | None = None
    program: str | None = None
    duration_years: Num = None
    annual_tuition: Num = None
    monthly_living: Num = None
    one_time_costs: Num = 0
    confirmed_funding: Num = 0
    potential_funding: Num = 0
    current_savings: Num = 0
    monthly_savings: Num = 0
    tuition_growth_pct: Num = 0
    living_growth_pct: Num = 0
    target_date: str | None = None
    notes: str | None = None


def _plan_values(body: PlanIn, today: date) -> dict:
    name = _text(body.name, 80)
    if not name:
        raise HTTPException(422, "Plan name is required.")
    data = body.model_dump()
    try:
        inp = sc.validate_inputs(data)
    except sc.CalcError as e:
        raise HTTPException(422, str(e))
    td = body.target_date or None
    if td:
        try:
            if date.fromisoformat(td) < today:
                raise HTTPException(422, "Target date must be today or later.")
        except ValueError:
            raise HTTPException(422, "Use the date format YYYY-MM-DD.")
    if body.university_id is not None and not db.q1("SELECT 1 FROM universities WHERE id = ?", (body.university_id,)):
        raise HTTPException(422, "Unknown university. Pick one from the list or use 'Other'.")
    v = {k: inp[k] for k in ss.NUM_FIELDS} | {"currency": inp["currency"], "name": name, "target_date": td,
         "destination_country": _text(body.destination_country, 80), "program": _text(body.program, 100),
         "university_other": _text(body.university_other, 100) if body.university_id is None else None,
         "university_id": body.university_id, "notes": _text(body.notes, 500)}
    return v


@router.get("/study-plans")
def list_plans(request: Request):
    u = require_user(request)
    return {"items": ss.list_plans(u["id"], _today(u))}


@router.post("/study-plans", status_code=201)
def create_plan(body: PlanIn, request: Request):
    u = require_user(request)
    today = _today(u)
    try:
        return ss.save_plan(u["id"], _plan_values(body, today), today)
    except LimitError as e:
        raise HTTPException(409, str(e))


@router.get("/study-plans/compare")
def compare_plans(request: Request, ids: str):
    u = require_user(request)
    try:
        wanted = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "ids must be a comma-separated list of numbers.")
    wanted = list(dict.fromkeys(wanted))
    if not 2 <= len(wanted) <= 3:
        raise HTTPException(422, "Choose two or three plans to compare.")
    today = _today(u)
    plans = [_nf(ss.get_plan(u["id"], i, today)) for i in wanted]
    return {"items": plans, "note": "Plans in different currencies are shown side by side and are NOT converted."}


@router.get("/study-plans/{pid}")
def get_plan(pid: int, request: Request):
    u = require_user(request)
    p = _nf(ss.get_plan(u["id"], pid, _today(u)))
    inp = ss.raw_inputs(p)
    p["sensitivity"] = [{"change_pct": r["change_pct"], "adjusted_total": str(r["adjusted_total"])}
                        for r in sc.sensitivity(sc.calculate(inp, _today(u))["total_cost"], p["currency"])]
    return p


@router.put("/study-plans/{pid}")
def update_plan(pid: int, body: PlanIn, request: Request):
    u = require_user(request)
    today = _today(u)
    return _nf(ss.save_plan(u["id"], _plan_values(body, today), today, pid))


@router.delete("/study-plans/{pid}")
def delete_plan(pid: int, request: Request):
    u = require_user(request)
    _nf(ss.delete_plan(u["id"], pid) or None)
    return {"ok": True}


@router.post("/study-plans/{pid}/duplicate", status_code=201)
def duplicate_plan(pid: int, request: Request):
    u = require_user(request)
    try:
        return _nf(ss.duplicate_plan(u["id"], pid, _today(u)))
    except LimitError as e:
        raise HTTPException(409, str(e))


class WhatIfIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tuition_change_pct: Num = 0
    living_change_pct: Num = 0
    extra_confirmed: Num = 0
    extra_potential: Num = 0
    monthly_savings: Num = None


@router.post("/study-plans/{pid}/whatif")
def whatif(pid: int, body: WhatIfIn, request: Request):
    """Stateless scenario: nothing is saved. Uses the plan's actual tuition and living values."""
    u = require_user(request)
    today = _today(u)
    p = _nf(ss.get_plan(u["id"], pid, today))
    try:
        r = sc.whatif(ss.raw_inputs(p), today, **body.model_dump())
    except sc.CalcError as e:
        raise HTTPException(422, str(e))
    conv = lambda d: {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}
    return {"baseline": conv(r["baseline"]), "scenario": conv(r["scenario"]), "total_change": str(r["total_change"]),
            "confirmed_gap_change": str(r["confirmed_gap_change"]), "potential_gap_change": str(r["potential_gap_change"]),
            "note": "Scenario only. Percentages are applied to your plan's own tuition and living values."}


# ---------------------------------------------------------------- quotes
class QuoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    send_currency: str
    receive_currency: str
    amount: Num
    rate: Num
    fee_percent: Num = 0
    fixed_fee: Num = 0
    convention: str = "added"
    delivery_days: str | None = None
    as_of: str | None = None          # when you saw this rate, e.g. 2026-10-18T14:30 (optional)


def _as_of(v):
    """Validate the optional 'seen at' time. Returns a normalised 'YYYY-MM-DDTHH:MM' string or None."""
    if v in (None, ""):
        return None
    try:
        t = datetime.fromisoformat(str(v).strip().replace("Z", ""))
    except ValueError:
        raise HTTPException(422, "The 'as of' time must look like 2026-10-18T14:30.")
    if t.tzinfo:
        t = t.astimezone(timezone.utc).replace(tzinfo=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if t > now + timedelta(days=1):
        raise HTTPException(422, "The 'as of' time cannot be in the future.")
    if t < now - timedelta(days=365):
        raise HTTPException(422, "The 'as of' time is more than a year old.")
    return t.strftime("%Y-%m-%dT%H:%M")


@router.post("/study-plans/{pid}/quotes", status_code=201)
def add_quote(pid: int, body: QuoteIn, request: Request):
    u = require_user(request)
    prov = _text(body.provider, 80)
    if not prov:
        raise HTTPException(422, "Provider name is required.")
    try:
        r = sc.quote(amount=body.amount, rate=body.rate, fee_percent=body.fee_percent, fixed_fee=body.fixed_fee, convention=body.convention,
                     send_ccy=body.send_currency, receive_ccy=body.receive_currency)
        v = {"provider": prov, "send_currency": r["send_currency"], "receive_currency": r["receive_currency"], "amount": sc.dec(body.amount, "Amount"),
             "rate": sc.dec(body.rate, "Exchange rate"), "fee_percent": sc.dec(body.fee_percent, "Fee percent", default=0),
             "fixed_fee": sc.dec(body.fixed_fee, "Fixed fee", default=0), "convention": body.convention, "delivery_days": _text(body.delivery_days, 30), "as_of": _as_of(body.as_of)}
    except sc.CalcError as e:
        raise HTTPException(422, str(e))
    try:
        _nf(ss.add_quote(u["id"], pid, v))
    except LimitError as e:
        raise HTTPException(409, str(e))
    return {"items": ss.list_quotes(u["id"], pid)}


@router.get("/study-plans/{pid}/quotes")
def quotes(pid: int, request: Request):
    u = require_user(request)
    _nf(ss.get_plan(u["id"], pid, _today(u)))
    return {"items": ss.list_quotes(u["id"], pid),
            "note": "These are rates YOU entered from banks' and providers' own websites. FinBridge does not fetch live bank prices. The market rate is a reference only."}


@router.get("/market-rate")
def market_rate(frm: str = Query(alias="from", max_length=3), to: str = Query(max_length=3)):
    """Reference mid-market rate (NOT a bank price). Says whether it is live or a fixed sample."""
    try:
        f, t = fx.norm(frm), fx.norm(to)
    except fx.FXError as e:
        raise HTTPException(422, str(e))
    return fx.market_info(f, t)


@router.delete("/study-quotes/{qid}")
def delete_quote(qid: int, request: Request):
    _nf(ss.delete_quote(require_user(request)["id"], qid) or None)
    return {"ok": True}


# ---------------------------------------------------------------- checklist & scholarships
class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    due_date: str | None = None
    done: bool | None = None
    plan_id: int | None = None


def _due(v):
    if v:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise HTTPException(422, "Use the date format YYYY-MM-DD.")
    return v or None


@router.get("/checklist")
def checklist(request: Request, plan_id: int | None = None):
    return {"items": ss.list_checklist(require_user(request)["id"], plan_id)}


@router.post("/checklist", status_code=201)
def add_check(body: CheckIn, request: Request):
    u = require_user(request)
    title = _text(body.title, 200)
    if not title:
        raise HTTPException(422, "Title is required.")
    try:
        _nf(ss.add_check(u["id"], body.plan_id, title, _due(body.due_date)) or None)
    except LimitError as e:
        raise HTTPException(409, str(e))
    return {"items": ss.list_checklist(u["id"], body.plan_id)}


@router.put("/checklist/{cid}")
def update_check(cid: int, body: CheckIn, request: Request):
    u = require_user(request)
    _nf(ss.update_check(u["id"], cid, body.done, _text(body.title, 200), _due(body.due_date)) or None)
    return {"ok": True}


@router.delete("/checklist/{cid}")
def delete_check(cid: int, request: Request):
    _nf(ss.delete_check(require_user(request)["id"], cid) or None)
    return {"ok": True}


@router.get("/scholarships")
def scholarships(request: Request, country: str = "", q: str = ""):
    require_user(request)
    return {"items": ss.scholarships(country[:60], q[:60]),
            "notice": "Directory only. Not funding: a scholarship counts as 'potential' until the awarding organisation confirms eligibility and amount. "
                      "Check each official site for current rules."}


# ---------------------------------------------------------------- PDF report
@router.get("/study-plans/{pid}/report.pdf")
def report(pid: int, request: Request):
    u = require_user(request)
    p = _nf(ss.get_plan(u["id"], pid, _today(u)))
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(501, "PDF reports need the 'reportlab' package (pip install reportlab).")
    r, c = p["result"], p["currency"]
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 56

    def line(text, size=10, bold=False, gap=15):
        nonlocal y
        if y < 70:
            pdf.showPage(); y = h - 56
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        pdf.drawString(48, y, re.sub(r"[^\x20-\x7E]", "?", str(text))[:110])
        y -= gap
    line("FinBridge Global AI - Study funding plan", 16, True, 24)
    line(f"Plan: {p['name']}   |   Currency: {c}", 11, True)
    line(f"University: {p['uni_name'] or p['university_other'] or 'not set'}   Program: {p['program'] or 'not set'}   Destination: {p['destination_country'] or 'not set'}")
    y -= 8
    line("Results (calculated on the server with exact decimal arithmetic)", 11, True)
    for label, key in [("Tuition total", "tuition_total"), ("Living total", "living_total"), ("One-time costs", "one_time_total"), ("TOTAL ESTIMATED COST", "total_cost"),
                       ("Confirmed funding", "confirmed_funding"), ("Current savings", "current_savings"), ("Confirmed gap", "confirmed_gap"),
                       ("Potential funding (NOT confirmed)", "potential_funding"), ("Gap if potential funding arrives", "potential_gap"),
                       ("Monthly saving needed", "monthly_required")]:
        line(f"{label}: {c} {r[key]}")
    line(f"Coverage by confirmed money: {r['coverage_confirmed_pct']}%   Months to target: {r['months_to_target']}")
    y -= 8
    line("Assumptions and limitations", 11, True)
    for t in ["Figures come from the values you entered; FinBridge did not look up tuition, rates or scholarships.",
              "Potential scholarships are not confirmed funding until the awarding organisation confirms them.",
              f"Rounding: {r['rounding']}. Growth rates are applied per academic year as you entered them.",
              "Decision support only. Not financial, legal or immigration advice. Verify everything with official sources.",
              "No money is moved by this application."]:
        line("- " + t, 9, False, 13)
    pdf.save()
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="finbridge-plan-{pid}.pdf"', "Cache-Control": "no-store"})
