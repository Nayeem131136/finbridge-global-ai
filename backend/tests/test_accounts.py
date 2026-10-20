"""Accounts, persistence, isolation, CSRF, reminders, wallet and the signed-in transfer flow."""
import base64
import io
import json
import time
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, seed, store, userctx
from app.llm import system_for
from app.main import app

PW = "Correct-horse-42"


@pytest.fixture(autouse=True)
def fresh():
    db.connect()
    seed.seed_universities()
    seed.seed_scholarships()
    for t in ("plan_quotes", "checklist_items", "study_plans", "notifications", "audit_events", "sandbox_records", "wallet_balances", "comparisons", "tuition_plans", "budgets",
              "profiles", "password_resets", "auth_sessions", "users"):
        db.run(f"DELETE FROM {t}")
    userctx.USER_SESSIONS.clear()
    auth.reset_rate_limits()
    yield


def client():
    return TestClient(app)


def signup(c=None, email="ana@example.com", name="Ana Rahman", pw=PW):
    c = c or client()
    r = c.post("/api/auth/signup", json={"name": name, "email": email, "password": pw, "confirm_password": pw, "accept_terms": True})
    assert r.status_code == 201, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    return c


# ------------------------------------------------------------ registration / login
def test_signup_sets_httponly_cookie_and_hashes_password():
    c = client()
    r = c.post("/api/auth/signup", json={"name": "Ana Rahman", "email": "Ana@Example.com", "password": PW, "confirm_password": PW, "accept_terms": True})
    assert r.status_code == 201
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert "token" not in r.text.lower() or "csrf" in r.text.lower()
    row = db.q1("SELECT * FROM users WHERE email = 'ana@example.com'")
    assert row and PW not in str(dict(row)) and len(row["pw_hash"]) == 64 and len(row["pw_salt"]) == 16
    raw = c.cookies.get("fb_session")
    assert raw and db.q1("SELECT 1 FROM auth_sessions WHERE token_hash = ?", (raw,)) is None      # only a hash is stored


@pytest.mark.parametrize("payload,code", [
    ({"password": "short1", "confirm_password": "short1"}, 422),
    ({"password": "onlyletterspassword", "confirm_password": "onlyletterspassword"}, 422),
    ({"password": PW, "confirm_password": PW + "x"}, 422),
    ({"email": "not-an-email"}, 422),
    ({"accept_terms": False}, 422),
    ({"name": "A"}, 422),
])
def test_signup_validation(payload, code):
    body = {"name": "Ana Rahman", "email": "ana@example.com", "password": PW, "confirm_password": PW, "accept_terms": True} | payload
    assert client().post("/api/auth/signup", json=body).status_code == code


def test_duplicate_email_rejected_case_insensitive():
    signup(email="ana@example.com")
    r = client().post("/api/auth/signup", json={"name": "Other Person", "email": "ANA@example.com", "password": PW, "confirm_password": PW, "accept_terms": True})
    assert r.status_code == 409


def test_login_logout_and_generic_errors():
    signup()
    c = client()
    bad = c.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrong-password-1"})
    unknown = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-1"})
    assert bad.status_code == unknown.status_code == 401 and bad.json() == unknown.json()
    ok = c.post("/api/auth/login", json={"email": "ana@example.com", "password": PW})
    assert ok.status_code == 200 and c.get("/api/auth/me").json()["authenticated"]
    c.headers["X-CSRF-Token"] = ok.json()["csrf"]
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").json() == {"authenticated": False}
    assert c.get("/api/profile").status_code == 401


def test_login_rate_limit():
    signup()
    c = client()
    codes = [c.post("/api/auth/login", json={"email": "ana@example.com", "password": f"bad-password-{i}"}).status_code for i in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    assert c.post("/api/auth/login", json={"email": "ana@example.com", "password": PW}).status_code == 429   # even the right password is held back


def test_session_expiry():
    c = signup()
    db.run("UPDATE auth_sessions SET expires_at = 1")
    assert c.get("/api/auth/me").json()["authenticated"] is False
    assert c.get("/api/dashboard").status_code == 401


# ------------------------------------------------------------ protection + CSRF
@pytest.mark.parametrize("path", ["/api/profile", "/api/dashboard", "/api/budgets", "/api/tuition-plans", "/api/comparisons", "/api/records", "/api/notifications"])
def test_private_endpoints_need_login(path):
    assert client().get(path).status_code == 401


def test_csrf_required_for_state_changes():
    c = signup()
    token = c.headers.pop("X-CSRF-Token")
    body = {"name": "Food", "income": 1000, "currency": "BDT", "expenses": {"food": 300}}
    assert c.post("/api/budgets", json=body).status_code == 403
    c.headers["X-CSRF-Token"] = "wrong"
    assert c.post("/api/budgets", json=body).status_code == 403
    c.headers["X-CSRF-Token"] = token
    assert c.post("/api/budgets", json=body).status_code == 201


# ------------------------------------------------------------ profile + directory
def test_profile_roundtrip_validation_and_clear():
    c = signup()
    uni = c.get("/api/universities", params={"q": "toronto"}).json()["items"][0]
    r = c.put("/api/profile", json={"home_country": "Bangladesh", "study_country": "Canada", "language": "bn", "currency": "bdt",
                                    "study_level": "master", "university_id": uni["id"], "program": "Computer Science", "monthly_income": 60000})
    assert r.status_code == 200
    p = c.get("/api/profile").json()["profile"]
    assert p["uni_name"] == "University of Toronto" and p["currency"] == "BDT" and p["language"] == "bn" and p["monthly_income"] == 60000
    for bad in ({"currency": "XXX"}, {"language": "fr"}, {"timezone": "Mars/Base"}, {"study_level": "wizard"}, {"tuition_date": "15-12-2026"},
                {"monthly_income": -5}, {"university_id": 99999}):
        assert c.put("/api/profile", json=bad).status_code == 422, bad
    c.put("/api/profile", json={"university_other": "My Small College"})
    p = c.get("/api/profile").json()["profile"]
    assert p["university_id"] is None and p["university_other"] == "My Small College"
    assert c.delete("/api/profile").json()["profile"]["program"] is None
    assert "NID" in c.get("/api/profile").json()["privacy"]


def test_university_search_and_filter():
    c = signup()
    assert any("Tsinghua" in u["name"] for u in c.get("/api/universities", params={"q": "tsing"}).json()["items"])
    items = c.get("/api/universities", params={"country": "gb"}).json()["items"]
    assert items and all(u["country"] == "GB" for u in items)
    assert c.get("/api/universities", params={"q": "%"}).json()["items"] == []          # wildcard is escaped, not matched
    assert "Tuition fees" in c.get("/api/universities").json()["notice"]


# ------------------------------------------------------------ budgets / tuition / comparisons CRUD + isolation
def test_budget_crud_and_isolation():
    a, b = signup(email="a@example.com"), signup(email="b@example.com", name="Bob Hasan")
    body = {"name": "October", "income": 60000, "currency": "BDT", "expenses": {"rent": 20000, "food": 12000}, "target_pct": 20}
    bid = a.post("/api/budgets", json=body).json()["id"]
    got = a.get(f"/api/budgets/{bid}").json()
    assert got["result"]["total_expenses"] == 32000
    assert a.put(f"/api/budgets/{bid}", json=body | {"name": "Nov", "expenses": {"rent": 25000}}).json()["name"] == "Nov"
    assert b.get(f"/api/budgets/{bid}").status_code == 404 and b.get("/api/budgets").json()["items"] == []
    assert b.put(f"/api/budgets/{bid}", json=body).status_code == 404 and b.delete(f"/api/budgets/{bid}").status_code == 404
    assert a.post("/api/budgets", json=body | {"income": 0}).status_code == 422
    assert a.post("/api/budgets", json=body | {"currency": "ZZZ"}).status_code == 422
    assert a.delete(f"/api/budgets/{bid}").status_code == 200 and a.get(f"/api/budgets/{bid}").status_code == 404


def test_tuition_plan_crud_progress_and_isolation():
    a, b = signup(email="a@example.com"), signup(email="b@example.com", name="Bob Hasan")
    due = (date.today() + timedelta(days=120)).isoformat()
    body = {"name": "Fall tuition", "total": 3000, "currency": "USD", "due_dates": [due], "home_currency": "BDT", "saved": 100000, "monthly_saving": 20000}
    r = a.post("/api/tuition-plans", json=body)
    assert r.status_code == 201
    p = r.json()
    assert 0 < p["progress_pct"] < 100 and p["plan"]["required_monthly"] > 0 and "estimates" in p["note"].lower()
    assert p["shortfall_monthly"] is not None
    assert a.put(f"/api/tuition-plans/{p['id']}", json=body | {"saved": 10 ** 9}).json()["progress_pct"] == 100
    assert b.get(f"/api/tuition-plans/{p['id']}").status_code == 404 and b.delete(f"/api/tuition-plans/{p['id']}").status_code == 404
    assert a.post("/api/tuition-plans", json=body | {"due_dates": ["2026-13-45"]}).status_code == 422
    assert a.post("/api/tuition-plans", json=body | {"total": -1}).status_code == 422
    past = a.post("/api/tuition-plans", json=body | {"due_dates": ["2020-01-01"]}).json()
    assert past["status"] == "past_due_dates" and past["plan"] is None
    assert a.delete(f"/api/tuition-plans/{p['id']}").status_code == 200


def test_saved_comparison_recomputed_server_side_and_isolated():
    a, b = signup(email="a@example.com"), signup(email="b@example.com", name="Bob Hasan")
    r = a.post("/api/comparisons", json={"amount": 1500, "to_currency": "GBP", "snapshot": {"quotes": "forged"}})
    assert r.status_code == 201
    c = r.json()
    assert c["snapshot"]["quotes"][0]["receive_currency"] == "GBP" and "Not a live offer" in c["note"]
    assert b.get("/api/comparisons").json()["items"] == [] and b.delete(f"/api/comparisons/{c['id']}").status_code == 404
    assert a.post("/api/comparisons", json={"amount": 10, "from_currency": "BDT", "to_currency": "BDT"}).status_code == 400
    assert a.delete(f"/api/comparisons/{c['id']}").status_code == 200


# ------------------------------------------------------------ wallet, signed-in transfer, persistence, audit
def test_wallet_deposit_withdraw_and_persistence():
    c = signup()
    assert c.post("/api/wallet/deposit", json={"amount": 5000, "currency": "BDT"}).json()["balances"]["BDT"] == 905000
    assert c.post("/api/wallet/deposit", json={"amount": 10 ** 9, "currency": "BDT"}).status_code == 400
    assert c.post("/api/wallet/withdraw", json={"amount": 100, "currency": "BDT", "secret": "wrong"}).status_code == 400
    ok = c.post("/api/wallet/withdraw", json={"amount": 1000, "currency": "BDT", "secret": PW})
    assert ok.status_code == 200 and ok.json()["balances"]["BDT"] == 904000
    assert c.post("/api/wallet/withdraw", json={"amount": 10 ** 8, "currency": "BDT", "secret": PW}).status_code == 400
    uid = db.q1("SELECT id FROM users")["id"]
    userctx.forget_user(uid)                                   # simulate a server restart
    assert c.get("/api/account").json()["balances"]["BDT"] == 904000
    kinds = [r["kind"] for r in c.get("/api/records").json()["items"]]
    assert kinds.count("deposit") == 1 and kinds.count("withdrawal") == 1
    assert c.get("/api/audit").json()["verify"]["ok"]


def test_signed_in_transfer_needs_password_and_is_persisted():
    c = signup()
    out = c.post("/api/chat", json={"message": "Pay 1500 GBP tuition to the university"}).json()
    assert out["signed_in"] and out["pending"]
    token = out["pending"]["token"]
    assert c.post("/api/confirm", json={"token": token, "pin": "1234"}).status_code == 400          # the demo PIN is NOT a password
    ok = c.post("/api/confirm", json={"token": token, "pin": PW})
    assert ok.status_code == 200 and ok.json()["transaction"]["status"].startswith("completed (sandbox)")
    assert c.post("/api/confirm", json={"token": token, "pin": PW}).status_code == 400              # replay is rejected
    recs = c.get("/api/records").json()
    assert recs["items"][0]["kind"] == "transfer" and "No real money" in recs["notice"]
    uid = db.q1("SELECT id FROM users")["id"]
    userctx.forget_user(uid)
    assert c.get("/api/audit").json()["verify"]["ok"] and c.get("/api/audit").json()["verify"]["count"] > 3
    assert c.get("/api/account").json()["balances"]["BDT"] < 900000
    dump = str(db.q("SELECT body FROM audit_events"))
    assert PW not in dump and "1234" not in dump


def test_three_wrong_passwords_lock_confirmation():
    c = signup()
    token = c.post("/api/chat", json={"message": "Pay 1500 GBP tuition to the university"}).json()["pending"]["token"]
    errs = [c.post("/api/confirm", json={"token": token, "pin": "nope"}).json()["detail"] for _ in range(3)]
    assert "locked" in errs[2].lower()
    assert c.post("/api/confirm", json={"token": token, "pin": PW}).status_code == 400


def test_confirmation_token_is_bound_to_its_session():
    a, b = signup(email="a@example.com"), signup(email="b@example.com", name="Bob Hasan")
    token = a.post("/api/chat", json={"message": "Pay 1500 GBP tuition to the university"}).json()["pending"]["token"]
    r = b.post("/api/confirm", json={"token": token, "pin": PW})
    assert r.status_code == 400 and "No such pending" in r.json()["detail"]


def test_guest_flow_still_works_with_demo_pin():
    c = client()
    out = c.post("/api/chat", json={"message": "Pay 1500 GBP tuition to the university"}).json()
    assert not out["signed_in"]
    r = c.post("/api/confirm", json={"session_id": out["session_id"], "token": out["pending"]["token"], "pin": "1234"})
    assert r.status_code == 200


def test_tamper_demo_is_labelled_simulated():
    c = signup()
    c.post("/api/chat", json={"message": "Best time to convert BDT to GBP?"})
    r = c.post("/api/audit/tamper-demo").json()
    assert r["simulated"] and r["copy_result"]["ok"] is False and r["real_result"]["ok"] is True and "SIMULATION" in r["note"]


# ------------------------------------------------------------ reminders / dashboard
def test_reminders_deduplicated_and_toggle():
    c = signup()
    due = (date.today() + timedelta(days=5)).isoformat()
    c.post("/api/tuition-plans", json={"name": "Spring", "total": 2000, "currency": "USD", "due_dates": [due], "home_currency": "BDT", "saved": 150000})
    first = c.get("/api/notifications").json()["items"]
    again = c.get("/api/notifications").json()["items"]
    kinds = sorted(n["kind"] for n in first)
    assert "tuition_due" in kinds and len(first) == len(again)
    assert "No email or push" in c.get("/api/notifications").json()["notice"]
    nid = first[0]["id"]
    assert c.post(f"/api/notifications/{nid}/read").status_code == 200
    assert all(n["id"] != nid for n in c.get("/api/notifications").json()["items"])
    c.put("/api/profile", json={"remind_tuition": False, "remind_savings": False, "remind_budget": False})
    db.run("DELETE FROM notifications")
    assert c.get("/api/notifications").json()["items"] == []


def test_dashboard_contents_and_empty_state():
    c = signup()
    d = c.get("/api/dashboard").json()
    assert d["name"] == "Ana Rahman" and d["budget"] is None and d["tuition"] == [] and d["records"] == [] and "estimates" in d["disclaimer"]
    c.post("/api/budgets", json={"name": "B", "income": 1000, "currency": "BDT", "expenses": {"food": 400}})
    assert c.get("/api/dashboard").json()["budget"]["name"] == "B"


# ------------------------------------------------------------ misc security
def test_account_deletion_removes_everything():
    c = signup()
    c.post("/api/budgets", json={"name": "B", "income": 1000, "currency": "BDT", "expenses": {"food": 400}})
    assert c.post("/api/account/delete", json={"password": "wrong-password-1"}).status_code == 403
    assert c.post("/api/account/delete", json={"password": PW}).status_code == 200
    for t in ("users", "profiles", "budgets", "wallet_balances", "audit_events"):
        assert db.q1(f"SELECT 1 FROM {t}") is None, t
    assert client().post("/api/auth/login", json={"email": "ana@example.com", "password": PW}).status_code == 401


def test_password_reset_flow(capsys):
    c = signup()
    r1 = client().post("/api/auth/forgot", json={"email": "ana@example.com"}).json()
    r2 = client().post("/api/auth/forgot", json={"email": "ghost@example.com"}).json()
    assert r1 == r2                                            # no account enumeration
    link = re.findall(r"#reset=([\w-]+)", capsys.readouterr().out)
    assert len(link) == 1                                      # only the existing account produced a link, printed to the server console
    c2 = client()
    assert c2.post("/api/auth/reset", json={"token": "bogus", "new_password": "Another-pass-77", "confirm_password": "Another-pass-77"}).status_code == 400
    assert c2.post("/api/auth/reset", json={"token": link[0], "new_password": "weak", "confirm_password": "weak"}).status_code == 400
    assert c2.post("/api/auth/reset", json={"token": link[0], "new_password": "Another-pass-77", "confirm_password": "Another-pass-77"}).status_code == 200
    assert c2.post("/api/auth/reset", json={"token": link[0], "new_password": "Third-pass-88x", "confirm_password": "Third-pass-88x"}).status_code == 400   # single use
    assert c.get("/api/auth/me").json()["authenticated"] is False                                    # old sessions signed out
    assert client().post("/api/auth/login", json={"email": "ana@example.com", "password": PW}).status_code == 401
    assert client().post("/api/auth/login", json={"email": "ana@example.com", "password": "Another-pass-77"}).status_code == 200


def test_security_headers_and_cors():
    r = client().get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    assert "default-src 'self'" in r.headers["content-security-policy"] and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"


def test_unexpected_errors_do_not_leak_details(monkeypatch):
    c = TestClient(app, raise_server_exceptions=False)
    s = signup(c)
    monkeypatch.setattr(store, "get_profile", lambda uid: (_ for _ in ()).throw(RuntimeError("secret path /etc/db")))
    r = s.get("/api/profile")
    assert r.status_code == 500 and "secret" not in r.text and "Traceback" not in r.text


def test_ai_context_has_no_personal_identifiers():
    c = signup()
    uni = c.get("/api/universities", params={"q": "oxford"}).json()["items"][0]
    c.put("/api/profile", json={"study_country": "United Kingdom", "currency": "BDT", "university_id": uni["id"], "monthly_income": 77777})
    s = userctx.user_session(db.q1("SELECT id FROM users")["id"])
    prompt = system_for(s)
    assert "University of Oxford" in prompt and "BDT" in prompt
    assert "Ana" not in prompt and "ana@example.com" not in prompt and "77777" not in prompt


# ------------------------------------------------------------ invoice upload
def _pdf(text):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    cv = canvas.Canvas(buf); cv.drawString(72, 720, text); cv.save()
    return buf.getvalue()


def test_invoice_pdf_extraction_and_limits():
    pytest.importorskip("pypdf"); pytest.importorskip("reportlab")
    c = signup()
    b64 = lambda raw: base64.b64encode(raw).decode()
    r = c.post("/api/invoice/extract", json={"filename": "inv.pdf", "content_b64": b64(_pdf("Beneficiary: Example University Bursar Amount 500 GBP"))})
    assert r.status_code == 200 and "Example University Bursar" in r.json()["text"] and "not stored" in r.json()["note"]
    assert c.post("/api/invoice/extract", json={"filename": "x.exe", "content_b64": b64(b"MZ\x90\x00 not a pdf")}).status_code == 415
    assert c.post("/api/invoice/extract", json={"filename": "x.png", "content_b64": b64(b"\x89PNG\r\n\x1a\n" + b"0" * 20)}).status_code == 501
    assert c.post("/api/invoice/extract", json={"filename": "x.pdf", "content_b64": "***not base64***"}).status_code == 422
    big = b"%PDF-" + b"0" * (2 * 1024 * 1024 + 10)
    assert c.post("/api/invoice/extract", json={"filename": "big.pdf", "content_b64": b64(big)}).status_code == 413
    assert client().post("/api/invoice/extract", json={"filename": "a.pdf", "content_b64": b64(_pdf("x"))}).status_code == 404   # no session at all


def test_migrations_are_recorded_and_idempotent():
    names = [r["name"] for r in db.q("SELECT name FROM schema_migrations")]
    assert names and names[0].startswith("001_")
    assert db.migrate(db.connect()) == []


def test_guest_wallet_creates_session_and_returns_id():
    client = TestClient(app)
    r = client.post("/api/wallet/deposit", json={"amount": 100, "currency": "USD"})
    assert r.status_code == 200 and r.json()["session_id"]
    sid = r.json()["session_id"]
    assert client.get(f"/api/account?session_id={sid}").json()["balances"]["USD"] >= 100


def test_reset_token_expires(capsys):
    signup()
    client().post("/api/auth/forgot", json={"email": "ana@example.com"})
    tok = re.findall(r"#reset=([\w-]+)", capsys.readouterr().out)[0]
    db.run("UPDATE password_resets SET expires_at = ?", (time.time() - 1,))
    r = client().post("/api/auth/reset", json={"token": tok, "new_password": "Another-pass-77", "confirm_password": "Another-pass-77"})
    assert r.status_code == 400 and "expired" in r.json()["detail"]
    assert client().post("/api/auth/login", json={"email": "ana@example.com", "password": PW}).status_code == 200   # password unchanged


def test_secrets_never_reach_the_audit_log():
    c = signup()
    c.post("/api/wallet/withdraw", json={"amount": 10, "currency": "BDT", "secret": "wrong-secret-XYZ"})
    c.post("/api/wallet/withdraw", json={"amount": 10, "currency": "BDT", "secret": PW})
    dump = json.dumps(c.get("/api/audit").json())
    assert PW not in dump and "wrong-secret-XYZ" not in dump and "withdrawal" in dump


def test_wallet_input_validation():
    c = signup()
    for body in ({"amount": -5, "currency": "BDT", "secret": PW}, {"amount": 0, "currency": "BDT", "secret": PW},
                 {"amount": 5, "currency": "XXX", "secret": PW}):
        assert c.post("/api/wallet/withdraw", json=body).status_code in (400, 422)
    assert c.post("/api/wallet/withdraw", json={"amount": 5_000_000, "currency": "BDT", "secret": PW}).status_code == 400   # over limit/balance
    assert c.post("/api/wallet/deposit", json={"amount": 10**9, "currency": "USD"}).status_code == 400                     # over deposit cap
    assert c.post("/api/wallet/deposit", json={"amount": "abc", "currency": "USD"}).status_code == 422


def test_other_users_notifications_and_comparisons_are_not_reachable():
    a = signup(email="a@example.com"); b = signup(email="b@example.com", name="Bee Khan")
    cid = a.post("/api/comparisons", json={"amount": 1000, "from_currency": "BDT", "to_currency": "GBP", "purpose": "tuition"}).json()["id"]
    assert b.delete(f"/api/comparisons/{cid}").status_code == 404
    assert b.post("/api/notifications/999999/read").status_code == 404
    assert b.get("/api/comparisons").json()["items"] == []


def test_upload_rejects_non_pdf_and_bad_base64():
    import base64
    c = signup()
    r = c.post("/api/invoice/extract", json={"filename": "x.exe", "content_b64": base64.b64encode(b"MZ\x90\x00 not a pdf").decode()})
    assert r.status_code in (415, 422)
    assert c.post("/api/invoice/extract", json={"filename": "x.pdf", "content_b64": "!!!not-base64!!!"}).status_code == 422
