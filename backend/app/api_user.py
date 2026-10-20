"""Authenticated API: auth, profile, directory, dashboard, plans, comparisons, reminders, wallet."""
import base64
import io
import json
import re
from datetime import date
from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from . import auth, fx, store, userctx
from .data import ALLOWED_PURPOSES, HOME_CURRENCIES
from . import invoice as invoice_mod
from .userctx import require_user, resolve

router = APIRouter(prefix="/api")
LEVELS = ["school", "foundation", "bachelor", "master", "phd", "other"]
_TZ = None


def _ccy(v: str) -> str:
    try:
        return fx.norm(v)
    except fx.FXError as e:
        raise ValueError(str(e))


def _text(v, n):
    if v is None:
        return None
    v = re.sub(r"\s+", " ", str(v)).strip()
    return v[:n] or None


# ================================================================== auth
class SignupIn(BaseModel):
    name: str = Field(max_length=100)
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)
    accept_terms: bool = False


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    new_password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)


class PasswordIn(BaseModel):
    password: str = Field(max_length=200)


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _login_response(response: Response, uid: int) -> dict:
    token, csrf = auth.new_session(uid)
    response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, secure=auth.PROD, samesite="lax", path="/")
    return me_payload(uid, csrf)


def me_payload(uid: int, csrf: str) -> dict:
    from . import db
    u = db.q1("SELECT id, email, name, created_at FROM users WHERE id = ?", (uid,))
    return {"authenticated": True, "csrf": csrf, "user": {"id": u["id"], "email": u["email"], "name": u["name"]},
            "profile": store.get_profile(uid)}


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, request: Request, response: Response):
    if body.password != body.confirm_password:
        raise HTTPException(422, "Passwords do not match.")
    try:
        uid = auth.create_user(body.name, body.email, body.password, body.accept_terms)
    except auth.AuthError as e:
        raise HTTPException(409 if "already exists" in str(e) else 422, str(e))
    s = userctx.user_session(uid)
    s.audit.append("account_created", {"user_id": uid})
    userctx.save(s)
    return _login_response(response, uid)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    try:
        uid = auth.login(body.email, body.password, _client(request))
    except auth.AuthError as e:
        raise HTTPException(429 if "Too many" in str(e) else 401, str(e))
    s = userctx.user_session(uid)
    s.audit.append("login", {"user_id": uid})
    userctx.save(s)
    return _login_response(response, uid)


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    got = userctx.current_user(request)
    if got:
        require_user(request)                      # CSRF check
        s = userctx.user_session(got[0]["id"])
        s.audit.append("logout", {"user_id": got[0]["id"]})
        userctx.save(s)
        auth.end_session(request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    got = userctx.current_user(request)
    if not got:
        return {"authenticated": False}
    return me_payload(got[0]["id"], got[1])


@router.post("/auth/forgot")
def forgot(body: ForgotIn, request: Request):
    auth.start_reset(body.email, base_url=str(request.base_url))
    return {"ok": True, "message": "If an account exists for that email, a reset link has been sent. "
            "(In development without email configured, the link is printed in the server console.)"}


@router.post("/auth/reset")
def reset(body: ResetIn):
    if body.new_password != body.confirm_password:
        raise HTTPException(422, "Passwords do not match.")
    try:
        auth.finish_reset(body.token, body.new_password)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "message": "Password updated. Please sign in."}


@router.post("/account/delete")
def delete_account(body: PasswordIn, request: Request, response: Response):
    user = require_user(request)
    s = userctx.user_session(user["id"])
    if not s._verify(body.password):
        raise HTTPException(403, "Wrong password.")
    store.delete_user(user["id"])
    userctx.forget_user(user["id"])
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


# ================================================================== profile + directory
class ProfileIn(BaseModel):
    home_country: str | None = Field(None, max_length=60)
    study_country: str | None = Field(None, max_length=60)
    language: str | None = Field(None, pattern="^(en|bn)$")
    currency: str | None = None
    timezone: str | None = None
    study_level: str | None = None
    university_id: int | None = None
    university_other: str | None = Field(None, max_length=100)
    program: str | None = Field(None, max_length=100)
    monthly_income: float | None = Field(None, ge=0, le=1e9)
    monthly_budget: float | None = Field(None, ge=0, le=1e9)
    tuition_date: str | None = None
    remind_tuition: bool | None = None
    remind_budget: bool | None = None
    remind_savings: bool | None = None

    @field_validator("currency")
    @classmethod
    def _c(cls, v):
        return None if v is None else _ccy(v)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        global _TZ
        if v is None:
            return v
        _TZ = _TZ or available_timezones()
        # Windows has no system time-zone database unless the `tzdata` package is installed;
        # then accept any well-formed Area/City name instead of rejecting every zone.
        ok = v in _TZ if _TZ else bool(re.fullmatch(r"[A-Za-z_]+(/[A-Za-z0-9_+\-]+){0,2}", v))
        if not ok:
            raise ValueError("Unknown time zone (use a name like Asia/Dhaka).")
        return v

    @field_validator("study_level")
    @classmethod
    def _lvl(cls, v):
        if v is not None and v not in LEVELS:
            raise ValueError("Study level must be one of: " + ", ".join(LEVELS))
        return v

    @field_validator("tuition_date")
    @classmethod
    def _date(cls, v):
        if v in (None, ""):
            return None
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError("Use the date format YYYY-MM-DD.")


@router.get("/profile")
def get_profile(request: Request):
    user = require_user(request)
    return {"user": {"name": user["name"], "email": user["email"]}, "profile": store.get_profile(user["id"]),
            "privacy": PRIVACY_NOTE}


PRIVACY_NOTE = ("FinBridge stores your profile and the plans you save in this application's database so they are there when you return. "
                "Financial fields are optional. We never ask for NID, passport, card numbers or bank passwords. "
                "If you use the AI assistant, only coarse hints (home currency, study country, university name) and your message text are sent to the AI provider, never your name, email, balances or saved amounts. "
                "You can clear optional profile fields or delete your account (and all its data) at any time.")


@router.put("/profile")
def put_profile(body: ProfileIn, request: Request):
    user = require_user(request)
    vals = body.model_dump(exclude_unset=True)
    for k in ("home_country", "study_country", "university_other", "program"):
        if k in vals:
            vals[k] = _text(vals[k], 100)
    if vals.get("university_id") is not None and not store.university_exists(vals["university_id"]):
        raise HTTPException(422, "Unknown university. Pick one from the list or choose 'Other / not listed'.")
    if vals.get("university_id") is not None:
        vals["university_other"] = None
    elif vals.get("university_other"):
        vals["university_id"] = None
    store.save_profile(user["id"], vals)
    s = userctx.user_session(user["id"])
    s.audit.append("profile_updated", {"fields": sorted(vals)})
    userctx.save(s)
    return {"profile": store.get_profile(user["id"])}


@router.delete("/profile")
def clear_profile(request: Request):
    user = require_user(request)
    store.clear_profile(user["id"])
    s = userctx.user_session(user["id"])
    s.audit.append("profile_cleared", {})
    userctx.save(s)
    return {"profile": store.get_profile(user["id"])}


@router.get("/universities")
def universities(q: str = "", country: str = "", limit: int = 30):
    return {"items": store.search_universities(q[:60], country[:2], max(1, min(limit, 60))),
            "countries": store.university_countries(),
            "notice": "Sample directory: names and locations only. Tuition fees, deadlines and payment details are not included; "
                      "always confirm them on the university's official website or with its finance office. Selecting a university does not verify enrollment."}


# ================================================================== budgets
class BudgetIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    income: float = Field(gt=0, le=1e9)
    currency: str = "BDT"
    expenses: dict[str, float] = Field(min_length=1, max_length=30)
    target_pct: float = Field(20.0, ge=0, le=90)
    _c = field_validator("currency")(lambda cls, v: _ccy(v))

    @field_validator("expenses")
    @classmethod
    def _e(cls, v):
        out = {}
        for k, a in v.items():
            k = re.sub(r"\s+", " ", k).strip()[:40]
            if not k:
                raise ValueError("Every expense needs a category name.")
            if not (0 <= a <= 1e9):
                raise ValueError("Expense amounts must be between 0 and 1,000,000,000.")
            out[k] = a
        return out


def _nf(x):
    if x is None:
        raise HTTPException(404, "Not found.")
    return x


@router.get("/budgets")
def list_budgets(request: Request):
    return {"items": store.list_budgets(require_user(request)["id"])}


@router.post("/budgets", status_code=201)
def create_budget(body: BudgetIn, request: Request):
    return store.save_budget(require_user(request)["id"], body.name, body.income, body.currency, body.expenses, body.target_pct)


@router.get("/budgets/{bid}")
def get_budget(bid: int, request: Request):
    return _nf(store.get_budget(require_user(request)["id"], bid))


@router.put("/budgets/{bid}")
def update_budget(bid: int, body: BudgetIn, request: Request):
    return _nf(store.save_budget(require_user(request)["id"], body.name, body.income, body.currency, body.expenses, body.target_pct, bid))


@router.delete("/budgets/{bid}")
def delete_budget(bid: int, request: Request):
    _nf(store.delete_budget(require_user(request)["id"], bid) or None)
    return {"ok": True}


# ================================================================== tuition plans
class TuitionIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    total: float = Field(gt=0, le=1e9)
    currency: str
    due_dates: list[str] = Field(min_length=1, max_length=12)
    home_currency: str = "BDT"
    saved: float = Field(0.0, ge=0, le=1e12)
    monthly_saving: float | None = Field(None, ge=0, le=1e12)
    _c = field_validator("currency", "home_currency")(lambda cls, v: _ccy(v))

    @field_validator("due_dates")
    @classmethod
    def _dd(cls, v):
        out = []
        for x in v:
            try:
                out.append(date.fromisoformat(x).isoformat())
            except ValueError:
                raise ValueError(f"'{x}' is not a valid date (use YYYY-MM-DD).")
        return sorted(set(out))


def _today(user) -> date:
    return store.today_for(store.get_profile(user["id"]).get("timezone"))


@router.get("/tuition-plans")
def list_tuition(request: Request):
    u = require_user(request)
    return {"items": store.list_tuition(u["id"], _today(u))}


@router.post("/tuition-plans", status_code=201)
def create_tuition(body: TuitionIn, request: Request):
    u = require_user(request)
    return store.save_tuition(u["id"], _today(u), body.model_dump())


@router.get("/tuition-plans/{pid}")
def get_tuition(pid: int, request: Request):
    u = require_user(request)
    return _nf(store.get_tuition(u["id"], pid, _today(u)))


@router.put("/tuition-plans/{pid}")
def update_tuition(pid: int, body: TuitionIn, request: Request):
    u = require_user(request)
    return _nf(store.save_tuition(u["id"], _today(u), body.model_dump(), pid))


@router.delete("/tuition-plans/{pid}")
def delete_tuition(pid: int, request: Request):
    _nf(store.delete_tuition(require_user(request)["id"], pid) or None)
    return {"ok": True}


# ================================================================== comparisons + records
class CompareIn(BaseModel):
    amount: float = Field(gt=0, le=10_000_000)
    from_currency: str = "BDT"
    to_currency: str
    purpose: str = "tuition"
    basis: str = Field("receive", pattern="^(receive|send)$")
    label: str | None = Field(None, max_length=80)
    _c = field_validator("from_currency", "to_currency")(lambda cls, v: _ccy(v))

    @field_validator("purpose")
    @classmethod
    def _p(cls, v):
        if v not in ALLOWED_PURPOSES:
            raise ValueError("Unsupported purpose.")
        return v


@router.get("/comparisons")
def list_comparisons(request: Request):
    return {"items": store.list_comparisons(require_user(request)["id"])}


@router.post("/comparisons", status_code=201)
def save_comparison(body: CompareIn, request: Request):
    u = require_user(request)
    try:
        c = store.save_comparison(u["id"], body.amount, body.from_currency, body.to_currency, body.purpose, body.basis, _text(body.label, 80))
    except ValueError as e:
        raise HTTPException(400, str(e))
    s = userctx.user_session(u["id"])
    s.audit.append("comparison_saved", {"id": c["id"]})
    userctx.save(s)
    return c


@router.delete("/comparisons/{cid}")
def delete_comparison(cid: int, request: Request):
    _nf(store.delete_comparison(require_user(request)["id"], cid) or None)
    return {"ok": True}


@router.get("/records")
def records(request: Request, limit: int = 30):
    return {"items": store.list_records(require_user(request)["id"], max(1, min(limit, 100))),
            "notice": "Sandbox records only. No real money was moved."}


# ================================================================== reminders
@router.get("/notifications")
def notifications(request: Request, all: bool = False):
    u = require_user(request)
    store.refresh_reminders(u["id"])
    return {"items": store.list_notifications(u["id"], all),
            "notice": "Reminders appear here in the app. No email or push message is sent unless a notification provider is configured."}


@router.post("/notifications/{nid}/read")
def read_notification(nid: int, request: Request):
    _nf(store.mark_notification(require_user(request)["id"], nid) or None)
    return {"ok": True}


# ================================================================== dashboard
@router.get("/dashboard")
def dashboard(request: Request):
    u = require_user(request)
    uid, today = u["id"], _today(u)
    store.refresh_reminders(uid)
    prof = store.get_profile(uid)
    budgets, tuition = store.list_budgets(uid), store.list_tuition(uid, today)
    s = userctx.user_session(uid)
    upcoming = sorted((p for p in tuition if p["next_due"]), key=lambda p: p["next_due"])
    return {"name": u["name"], "profile": prof, "balances": s.balances, "today": today.isoformat(),
            "budget": budgets[0] if budgets else None, "budget_count": len(budgets),
            "tuition": tuition[:5], "tuition_count": len(tuition), "upcoming": upcoming[:3],
            "comparisons": store.list_comparisons(uid)[:5], "records": store.list_records(uid, 8),
            "notifications": store.list_notifications(uid),
            "fx_source": fx.source_label(),
            "disclaimer": "Figures come from what you entered and illustrative sandbox data. They are estimates, not financial advice, and no real payment has been made."}


# ================================================================== invoice upload (PDF text only)
MAX_UPLOAD = 2 * 1024 * 1024


class UploadIn(BaseModel):
    filename: str = Field(max_length=120)
    content_b64: str = Field(max_length=MAX_UPLOAD * 2)


@router.post("/invoice/extract")
def extract_invoice(body: UploadIn, request: Request, session_id: str | None = None):
    resolve(request, session_id)                      # signed-in user or existing demo session only
    try:
        raw = base64.b64decode(body.content_b64, validate=True)
    except Exception:
        raise HTTPException(422, "The file could not be read.")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (limit 2 MB).")
    if raw[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise HTTPException(501, "PDF reading is not installed on this server (pip install pypdf). Please paste the invoice text instead.")
        try:
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise HTTPException(422, "Encrypted PDFs are not supported. Please paste the invoice text instead.")
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages[:5]).strip()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "Could not read this PDF. Please paste the invoice text instead.")
        if not text:
            raise HTTPException(422, "No text found in this PDF (it may be a scan). OCR is not available here; please paste the invoice text instead.")
        return {"text": text[:6000], "note": "Text extracted in memory; the file was not stored. Treat it as untrusted."}
    if raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:3] == b"\xff\xd8\xff":
        raise HTTPException(501, "Image OCR is not available in this prototype. Please paste the invoice text instead.")
    raise HTTPException(415, "Only text-based PDF files are supported. Please paste the invoice text instead.")
