"""FastAPI app: chat, confirm/cancel, wallet, audit, accounts and the saved-plans API. Serves the frontend too."""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, db, fx, remit, seed, userctx
from .agent import Agent
from .api_user import router as user_router
from .api_study import router as study_router
from .data import ALLOWED_PURPOSES
from .llm import build_planner

log = logging.getLogger("finbridge")
PROD = auth.PROD
OFFLINE = os.getenv("FINBRIDGE_OFFLINE") == "1"          # forced offline test mode (no live FX, no AI provider)
LIVE_FX = not OFFLINE and os.getenv("FINBRIDGE_LIVE_FX", "1") != "0"


async def _refresh_loop():
    while True:
        await asyncio.to_thread(fx.refresh_live)         # never raises; keeps the last good rates on failure
        await asyncio.sleep(1800)


@asynccontextmanager
async def lifespan(_app):
    db.connect()
    seed.seed_universities()
    seed.seed_scholarships()
    task = asyncio.create_task(_refresh_loop()) if LIVE_FX else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="FinBridge API", version="2.0.0", lifespan=lifespan, docs_url=None if PROD else "/api/docs", redoc_url=None, openapi_url=None if PROD else "/api/openapi.json")

# The frontend is served from the same origin, so CORS is only needed for a separately hosted frontend.
_origins = [o.strip() for o in os.getenv("FINBRIDGE_CORS", "" if PROD else "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update({"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                         "Referrer-Policy": "no-referrer", "Permissions-Policy": "camera=(), geolocation=(), microphone=(self)"})
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    if PROD:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.exception_handler(RequestValidationError)
async def validation_error(_req, exc: RequestValidationError):
    msgs = []
    for e in exc.errors()[:4]:
        loc = ".".join(str(x) for x in e["loc"] if x not in ("body", "query"))
        msgs.append(f"{loc + ': ' if loc else ''}{str(e['msg']).removeprefix('Value error, ')}")
    return JSONResponse({"detail": "; ".join(msgs) or "Invalid input."}, status_code=422)


@app.exception_handler(Exception)
async def unexpected(_req, exc: Exception):
    log.exception("Unhandled error")                      # details stay in the server log
    return JSONResponse({"detail": "Something went wrong on the server. Please try again."}, status_code=500)


RATE: dict[str, list[float]] = {}          # session -> recent request timestamps
agent = Agent(build_planner())


class ChatIn(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=8000)
    lang: str = Field(default="en", pattern="^(en|bn)$")


class ConfirmIn(BaseModel):
    session_id: str | None = None
    token: str = Field(max_length=100)
    pin: str = Field(max_length=200)          # demo PIN for guests, account password for signed-in users


class CancelIn(BaseModel):
    session_id: str | None = None
    token: str = Field(max_length=100)


class MoneyIn(BaseModel):
    session_id: str | None = None
    amount: float = Field(gt=0, le=1e12)
    currency: str = Field(max_length=3)
    source: str = Field("your linked bank account (simulated)", max_length=60)
    secret: str = Field("", max_length=200)


@app.get("/api/health")
def health():
    info = agent.llm.describe() if agent.llm else {}
    return {"ok": True, "mode": "llm" if agent.llm else "rules", "offline": OFFLINE, "sandbox": True,
            "provider": info.get("provider"), "model": info.get("model"),
            "llm_state": info.get("state", "none"), "llm_error": info.get("last_error", ""), "fx_source": fx.SOURCE,
            "fx_updated": fx.UPDATED, "live_fx_enabled": LIVE_FX, "env": "production" if PROD else "development"}


_LAST_PROBE = [0.0]


@app.post("/api/llm/check")
def llm_check():
    """One tiny REAL request to Groq (no tools, no personal data). Updates the status shown in the UI."""
    if not agent.llm:
        return {"ok": False, "state": "none", "error": "No GROQ_API_KEY configured."}
    if time.time() - _LAST_PROBE[0] < 5:
        raise HTTPException(429, "Please wait a few seconds between checks.")
    _LAST_PROBE[0] = time.time()
    p = agent.llm
    try:
        p.ping()
        p.state, p.last_error = "ok", ""
    except Exception as e:                                           # noqa: BLE001
        p.state, p.last_error = "error", str(e)[:200]
    return {"ok": p.state == "ok", "state": p.state, "error": p.last_error, "model": p.model}


@app.post("/api/chat")
def chat(body: ChatIn, request: Request):
    s, user = userctx.resolve(request, body.session_id, create_guest=True)
    if not user:
        s.lang = body.lang
    now = time.time()
    hits = [t for t in RATE.get(s.id, []) if now - t < 60]
    if len(hits) >= 30:
        raise HTTPException(429, "Too many messages. Please wait a minute.")
    RATE[s.id] = hits + [now]
    out = agent.handle(s, body.message)
    userctx.save(s)
    return {"session_id": s.id, **out, "balances": s.balances, "signed_in": bool(user)}


@app.post("/api/confirm")
def confirm(body: ConfirmIn, request: Request):
    s, _ = userctx.resolve(request, body.session_id)
    res = s.confirm(body.token, body.pin)
    # never log the PIN/password; record only the outcome
    s.audit.append("confirmation_result", {"ok": res["ok"], "error": res.get("error"), "ref": (res.get("transaction") or {}).get("ref")})
    userctx.save(s)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


@app.post("/api/cancel")
def cancel(body: CancelIn, request: Request):
    s, _ = userctx.resolve(request, body.session_id)
    ok = s.cancel(body.token)
    s.audit.append("confirmation_result", {"ok": False, "cancelled": ok})
    userctx.save(s)
    return {"ok": ok}


@app.get("/api/account")
def account(request: Request, session_id: str | None = None):
    s, _ = userctx.resolve(request, session_id)
    return {"balances": s.balances, "transactions": s.transactions, "ledger": s.ledger}


@app.post("/api/wallet/deposit")
def deposit(body: MoneyIn, request: Request):
    s, _ = userctx.resolve(request, body.session_id, create_guest=True)
    try:
        res = s.deposit(body.amount, body.currency, body.source)
    except fx.FXError as e:
        raise HTTPException(422, str(e))
    s.audit.append("deposit", {"ok": res["ok"], "ref": (res.get("entry") or {}).get("ref"), "currency": body.currency.upper()})
    userctx.save(s)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res | {"session_id": s.id}


@app.post("/api/wallet/withdraw")
def withdraw(body: MoneyIn, request: Request):
    s, _ = userctx.resolve(request, body.session_id, create_guest=True)
    try:
        res = s.withdraw(body.amount, body.currency, body.secret)
    except fx.FXError as e:
        raise HTTPException(422, str(e))
    s.audit.append("withdrawal", {"ok": res["ok"], "ref": (res.get("entry") or {}).get("ref"), "currency": body.currency.upper()})
    userctx.save(s)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res | {"session_id": s.id}


@app.get("/api/audit")
def audit(request: Request, session_id: str | None = None):
    s, _ = userctx.resolve(request, session_id)
    return {"verify": s.audit.verify(), "entries": s.audit.entries[-100:]}  # details were masked at write time


@app.post("/api/audit/tamper-demo")
def tamper_demo(request: Request, session_id: str | None = None):
    s, _ = userctx.resolve(request, session_id)
    out = s.audit.tamper_demo()
    return out | {"simulated": True, "note": "SIMULATION: one entry is edited in a temporary copy. Your stored log is never modified."}


@app.get("/api/compare")
def compare(amount: float, frm: str = "BDT", to: str = "USD", purpose: str = "tuition", basis: str = "receive"):
    """Direct cost comparison for the Cost Explorer (no AI involved, nothing is saved or sent)."""
    if not (0 < amount <= 10_000_000) or purpose not in ALLOWED_PURPOSES or basis not in ("receive", "send"):
        raise HTTPException(422, "Invalid amount, purpose or basis.")
    try:
        res = remit.compare(amount, frm, to, purpose, basis)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return res | {"from": res["quotes"][0]["send_currency"], "to": res["quotes"][0]["receive_currency"]}


app.include_router(user_router)
app.include_router(study_router)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
