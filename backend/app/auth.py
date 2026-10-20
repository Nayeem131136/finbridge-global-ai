"""Authentication: password hashing (scrypt), cookie sessions, CSRF, login rate limiting, password reset.

Security notes
- Passwords are stored only as salted scrypt hashes (hashlib.scrypt from the Python standard library).
- The session cookie holds a random token; only its SHA-256 is stored in the database.
- Cookies are HttpOnly, SameSite=Lax, and Secure when FINBRIDGE_ENV=production.
- State-changing requests authenticated by cookie must carry the X-CSRF-Token header (double-submit with a per-session secret).
- Login attempts are rate limited per (client, email) and per client. The limiter is in memory (single process).
"""
import hashlib
import logging
import os
import re
import secrets
import smtplib
import time
from email.message import EmailMessage

from . import db

log = logging.getLogger("finbridge.auth")
PROD = os.getenv("FINBRIDGE_ENV", "development").lower() == "production"
COOKIE = "fb_session"
SESSION_SECONDS = int(float(os.getenv("FINBRIDGE_SESSION_HOURS", "12")) * 3600)
RESET_SECONDS = 30 * 60
_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_COMMON = {"password123", "qwerty12345", "1234567890", "iloveyou123", "welcome1234", "password1234", "letmein1234"}


class AuthError(ValueError):
    pass


# ----------------------------------------------------------------- passwords
def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, str]:
    salt = salt or secrets.token_bytes(16)
    return salt, hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32).hex()


def verify_password(password: str, salt: bytes, expected: str) -> bool:
    return secrets.compare_digest(hash_password(password, salt)[1], expected)


def check_email(email: str) -> str:
    email = (email or "").strip().lower()
    if len(email) > 254 or not _EMAIL.match(email):
        raise AuthError("Enter a valid email address.")
    return email


def check_password(password: str, email: str = "", name: str = "") -> None:
    if len(password or "") < 10:
        raise AuthError("Password must be at least 10 characters.")
    if len(password) > 128:
        raise AuthError("Password must be at most 128 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise AuthError("Password must contain at least one letter and one digit.")
    low = password.lower()
    if low in _COMMON or (email and low == email.split("@")[0].lower()) or (name and len(name) > 3 and name.lower() in low):
        raise AuthError("That password is too easy to guess. Choose a less predictable one.")


# ----------------------------------------------------------------- users
def create_user(name: str, email: str, password: str, accepted_terms: bool) -> int:
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not (2 <= len(name) <= 80):
        raise AuthError("Enter your full name (2 to 80 characters).")
    email = check_email(email)
    check_password(password, email, name)
    if not accepted_terms:
        raise AuthError("You must accept the privacy policy and terms to create an account.")
    salt, h = hash_password(password)
    try:
        with db.tx() as c:
            cur = c.execute("INSERT INTO users(email, name, pw_salt, pw_hash, accepted_terms_at) VALUES (?,?,?,?, datetime('now'))",
                            (email, name, salt, h))
            uid = cur.lastrowid
            c.execute("INSERT INTO profiles(user_id) VALUES (?)", (uid,))
        return uid
    except Exception as e:
        if "UNIQUE" in str(e):
            raise AuthError("An account with this email already exists. Try signing in.")
        raise


# ----------------------------------------------------------------- rate limiting
_FAILS: dict[str, list[float]] = {}
WINDOW, MAX_PER_ACCOUNT, MAX_PER_CLIENT = 300, 5, 20


def _recent(key: str) -> list[float]:
    now = time.time()
    _FAILS[key] = [t for t in _FAILS.get(key, []) if now - t < WINDOW]
    return _FAILS[key]


def check_rate(client: str, email: str) -> None:
    if len(_recent(f"a:{client}:{email}")) >= MAX_PER_ACCOUNT or len(_recent(f"c:{client}")) >= MAX_PER_CLIENT:
        raise AuthError("Too many failed attempts. Please wait a few minutes and try again.")


def record_fail(client: str, email: str) -> None:
    _recent(f"a:{client}:{email}").append(time.time())
    _recent(f"c:{client}").append(time.time())


def reset_rate_limits() -> None:           # used by tests
    _FAILS.clear()


def login(email: str, password: str, client: str) -> int:
    email = (email or "").strip().lower()
    check_rate(client, email)
    row = db.q1("SELECT id, pw_salt, pw_hash FROM users WHERE email = ?", (email,))
    ok = verify_password(password or "", row["pw_salt"], row["pw_hash"]) if row else (hash_password("x") and False)
    if not ok:
        record_fail(client, email)
        raise AuthError("Wrong email or password.")       # same message for unknown email and wrong password
    db.run("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (row["id"],))
    return row["id"]


# ----------------------------------------------------------------- sessions
def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(user_id: int) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    with db.tx() as c:
        c.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (time.time(),))
        c.execute("INSERT INTO auth_sessions(token_hash, user_id, csrf, expires_at) VALUES (?,?,?,?)",
                  (_h(token), user_id, csrf, time.time() + SESSION_SECONDS))
    return token, csrf


def session_from_token(token: str | None):
    """Return (user_row, csrf) or None when the cookie is missing, unknown or expired."""
    if not token:
        return None
    row = db.q1("SELECT s.csrf, s.expires_at, u.* FROM auth_sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (_h(token),))
    if not row:
        return None
    if row["expires_at"] < time.time():
        end_session(token)
        return None
    return row, row["csrf"]


def end_session(token: str | None) -> None:
    if token:
        db.run("DELETE FROM auth_sessions WHERE token_hash = ?", (_h(token),))


def end_all_sessions(user_id: int) -> None:
    db.run("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))


# ----------------------------------------------------------------- password reset
def start_reset(email: str, base_url: str = "") -> None:
    """Always returns silently (no account enumeration). Delivers the link by SMTP when configured;
    in development without SMTP the link is printed to the SERVER console only."""
    email = (email or "").strip().lower()
    row = db.q1("SELECT id FROM users WHERE email = ?", (email,)) if _EMAIL.match(email) else None
    if not row:
        return
    token = secrets.token_urlsafe(32)
    db.run("INSERT INTO password_resets(token_hash, user_id, expires_at) VALUES (?,?,?)",
                         (_h(token), row["id"], time.time() + RESET_SECONDS))
    link = f"{base_url.rstrip('/')}/#reset={token}"
    if os.getenv("SMTP_HOST"):
        try:
            _send_mail(email, "FinBridge password reset", f"Use this link within 30 minutes to reset your password:\n{link}\n\nIf you did not ask for this, ignore this email.")
            log.info("Password reset email sent to %s", email)
        except Exception as e:                                     # never leak details to the client
            log.error("Could not send reset email: %s", type(e).__name__)
    elif not PROD:
        print(f"\n[DEV ONLY] Password reset link for {email}:\n  {link}\n", flush=True)
    else:
        log.warning("Password reset requested but SMTP is not configured; no email was sent.")


def finish_reset(token: str, new_password: str) -> None:
    row = db.q1("SELECT p.user_id, p.expires_at, p.used, u.email, u.name FROM password_resets p JOIN users u ON u.id = p.user_id WHERE p.token_hash = ?", (_h(token or ""),))
    if not row or row["used"] or row["expires_at"] < time.time():
        raise AuthError("This reset link is invalid or has expired. Request a new one.")
    check_password(new_password, row["email"], row["name"])
    salt, h = hash_password(new_password)
    with db.tx() as c:
        c.execute("UPDATE users SET pw_salt = ?, pw_hash = ? WHERE id = ?", (salt, h, row["user_id"]))
        c.execute("UPDATE password_resets SET used = 1 WHERE token_hash = ?", (_h(token),))
        c.execute("DELETE FROM auth_sessions WHERE user_id = ?", (row["user_id"],))      # sign out everywhere


def _send_mail(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@localhost")), to, subject
    msg.set_content(body)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=10) as s:
        s.starttls()
        if os.getenv("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        s.send_message(msg)
