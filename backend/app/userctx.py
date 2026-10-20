"""Resolves who is calling: a signed-in user (cookie) or an anonymous demo guest (session_id).

Signed-in users get a long-lived in-memory Session hydrated from the database (balances, audit chain, today's transfers)
and persisted back after every state change. Guests get a throw-away in-memory Session with the public demo PIN.
"""
import secrets

from fastapi import HTTPException, Request

from . import auth, db, store
from .session import Session

GUESTS: dict[str, Session] = {}
MAX_GUESTS = 500
USER_SESSIONS: dict[int, Session] = {}
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def guest_session(sid: str | None, create: bool = True) -> Session:
    if sid and sid in GUESTS:
        return GUESTS[sid]
    if not create:
        raise HTTPException(404, "Unknown session")
    if len(GUESTS) >= MAX_GUESTS:
        GUESTS.pop(next(iter(GUESTS)))
    s = Session()
    GUESTS[s.id] = s
    return s


def _verifier(uid: int):
    def check(password: str) -> bool:
        row = db.q1("SELECT pw_salt, pw_hash FROM users WHERE id = ?", (uid,))
        return bool(row) and auth.verify_password(password, row["pw_salt"], row["pw_hash"])
    return check


def user_session(uid: int) -> Session:
    s = USER_SESSIONS.get(uid)
    if s is None:
        s = Session()
        s.uid, s.verifier = uid, _verifier(uid)
        store.load_session_state(uid, s)
        USER_SESSIONS[uid] = s
    prof = store.get_profile(uid)
    s.lang = prof.get("language", "en")
    s.today = store.today_for(prof.get("timezone"))
    s.context = {"home_currency": prof.get("currency"), "study_country": prof.get("study_country"), "university": prof.get("uni_name") or prof.get("university_other")}
    return s


def forget_user(uid: int) -> None:
    USER_SESSIONS.pop(uid, None)


def csrf_ok(request: Request, csrf: str) -> bool:
    return secrets.compare_digest(request.headers.get("x-csrf-token", ""), csrf)


def current_user(request: Request):
    """Return (user_row, csrf) for a valid cookie, else None. Does NOT enforce CSRF."""
    return auth.session_from_token(request.cookies.get(auth.COOKIE))


def require_user(request: Request):
    got = current_user(request)
    if not got:
        raise HTTPException(401, "Please sign in.")
    user, csrf = got
    if request.method in UNSAFE and not csrf_ok(request, csrf):
        raise HTTPException(403, "Security check failed (missing or wrong CSRF token). Reload the page and try again.")
    return user


def resolve(request: Request, session_id: str | None = None, create_guest: bool = False):
    """(Session, user_row_or_None). A valid cookie always wins over a guest session_id."""
    got = current_user(request)
    if got:
        user = require_user(request)
        return user_session(user["id"]), user
    return guest_session(session_id, create=create_guest), None


def save(s: Session) -> None:
    if s.uid:
        store.persist_session(s.uid, s)
