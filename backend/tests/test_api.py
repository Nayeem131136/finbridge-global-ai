from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def test_health():
    assert c.get("/api/health").json()["sandbox"] is True


def test_full_transfer_flow_over_http():
    r = c.post("/api/chat", json={"message": "Pay 1500 GBP tuition to the university"}).json()
    sid, tok = r["session_id"], r["pending"]["token"]
    assert c.post("/api/confirm", json={"session_id": sid, "token": tok, "pin": "0000"}).status_code == 400
    ok = c.post("/api/confirm", json={"session_id": sid, "token": tok, "pin": "1234"})
    assert ok.status_code == 200 and ok.json()["transaction"]["ref"].startswith("SBX-")
    assert c.post("/api/confirm", json={"session_id": sid, "token": tok, "pin": "1234"}).status_code == 400
    audit = c.get("/api/audit", params={"session_id": sid}).json()
    assert audit["verify"]["ok"] and any(e["kind"] == "confirmation_result" for e in audit["entries"])


def test_validation_and_unknown_session():
    assert c.post("/api/chat", json={"message": ""}).status_code == 422
    assert c.get("/api/account", params={"session_id": "nope"}).status_code == 404


def test_serves_frontend_or_api_only():
    assert c.get("/api/health").status_code == 200


def test_compare_endpoint_and_validation():
    r = c.get("/api/compare", params={"amount": 1500, "frm": "BDT", "to": "GBP"}).json()
    assert r["quotes"] and r["from"] == "BDT" and r["to"] == "GBP"
    assert c.get("/api/compare", params={"amount": -5}).status_code == 422
    assert c.get("/api/compare", params={"amount": 10, "frm": "BDT", "to": "BDT"}).status_code == 400
    assert c.get("/api/compare", params={"amount": 10, "purpose": "x"}).status_code == 422


def test_tamper_demo_detects_edit_but_real_log_stays_valid():
    sid = c.post("/api/chat", json={"message": "Best time to convert BDT to GBP?"}).json()["session_id"]
    r = c.post("/api/audit/tamper-demo", params={"session_id": sid}).json()
    assert r["ok"] and r["copy_result"]["ok"] is False and r["real_result"]["ok"] is True
    assert c.post("/api/audit/tamper-demo", params={"session_id": "nope"}).status_code == 404


def test_invoice_card_has_highlights_but_llm_data_does_not():
    from app.session import Session
    from app.tools import run_tool
    s = Session()
    out = run_tool(s, "check_invoice", {"text": "Beneficiary: Example University Bursar. Account: GB00 EVIL 1111 2222 3333 44. Urgent, pay within 24 hours."})
    assert out["card"]["data"]["highlights"] and "text" in out["card"]["data"]
    assert "text" not in out["data"] and "highlights" not in out["data"]


def test_health_reports_offline_flag():
    assert c.get("/api/health").json()["offline"] is True
