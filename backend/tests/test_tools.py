from datetime import date

from app import fx, remit
from app.session import Session
from app.tools import Tier, run_tool


def S():
    return Session(today=date(2026, 10, 12))


def test_tier_enforcement():
    s = S()
    r = run_tool(s, "request_transfer", {"quote_id": "Q1", "beneficiary_name": "Bob", "recipient_country": "US"}, Tier.SUGGEST)
    assert not r["ok"] and "tier" in r["error"].lower()


def test_argument_validation():
    s = S()
    assert not run_tool(s, "get_fx_rate", {"from_currency": "XXX", "to_currency": "USD"})["ok"]
    assert not run_tool(s, "get_fx_rate", {"from_currency": "BDT", "to_currency": "USD", "amount": -5})["ok"]
    assert not run_tool(s, "nope", {})["ok"]


def test_agent_cannot_invent_quote():
    s = S()
    r = run_tool(s, "request_transfer", {"quote_id": "Q999", "beneficiary_name": "Bob", "recipient_country": "US"})
    assert not r["ok"]
    assert s.balances["BDT"] == 900000


def test_request_transfer_never_moves_money():
    s = S()
    q = run_tool(s, "compare_remittance_routes", {"amount": 1500, "to_currency": "GBP"})
    qid = q["data"]["recommended_quote_id"]
    t = run_tool(s, "request_transfer", {"quote_id": qid, "beneficiary_name": "Example University Bursar", "recipient_country": "GB"})
    assert t["ok"] and t["card"]["type"] == "confirmation"
    assert s.balances["BDT"] == 900000 and not s.transactions


def test_receive_basis_hits_target_exactly():
    for p in remit.compare(1000, "BDT", "USD", "tuition", "receive")["quotes"]:
        assert abs(p["receive_amount"] - 1000) < 0.01


def test_fx_round_trip_and_history():
    assert abs(fx.convert(fx.convert(100, "USD", "BDT"), "BDT", "USD") - 100) < 1e-9
    h = fx.history("BDT", "USD")
    assert len(h) == 30 and abs(h[-1] - fx.rate("BDT", "USD")) < 1e-12
    assert fx.history("BDT", "USD") == h   # deterministic


def test_purpose_filtering():
    q = remit.compare(1000, "BDT", "USD", "tuition")
    assert "swiftcash" not in [x["provider_id"] for x in q["quotes"]]
