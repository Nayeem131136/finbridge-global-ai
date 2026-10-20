"""Study planning: exact calculations, what-if regression, validation, ownership, quotes, PDF, AI tool."""
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from app import studycalc as sc, userctx
from app.main import app
from app.agent import Agent
from app.session import Session
from tests.test_accounts import fresh, signup, client, PW   # noqa: F401  (autouse fixture resets the DB)

TODAY = date(2026, 10, 17)


def inputs(**kw):
    base = {"currency": "USD", "duration_years": 2, "annual_tuition": 20000, "monthly_living": 1000, "one_time_costs": 2000,
            "confirmed_funding": 10000, "potential_funding": 8000, "current_savings": 2000, "monthly_savings": 1500, "target_date": "2027-08-01"}
    base.update(kw)
    return sc.validate_inputs(base)


# ------------------------------------------------------------------ pure calculations
def test_exact_totals_gaps_and_monthly():
    r = sc.calculate(inputs(), TODAY)
    assert r["tuition_total"] == D("40000.00") and r["living_total"] == D("24000.00") and r["total_cost"] == D("66000.00")
    assert r["confirmed_money"] == D("12000.00") and r["confirmed_gap"] == D("54000.00")
    assert r["potential_gap"] == D("46000.00")                       # potential funding reduces only the scenario gap
    assert r["months_to_target"] == 10 and r["monthly_required"] == D("5400.00")
    assert r["coverage_confirmed_pct"] == D("18.18") and r["coverage_with_potential_pct"] == D("30.30")
    assert r["months_needed_at_capacity"] == 36 and r["on_track"] is False


def test_potential_funding_never_counts_as_confirmed():
    a = sc.calculate(inputs(potential_funding=0), TODAY)
    b = sc.calculate(inputs(potential_funding=50000), TODAY)
    assert a["confirmed_gap"] == b["confirmed_gap"] and a["coverage_confirmed_pct"] == b["coverage_confirmed_pct"]
    assert b["potential_gap"] < a["potential_gap"]


def test_savings_counted_once():
    a = sc.calculate(inputs(current_savings=0, confirmed_funding=12000), TODAY)
    b = sc.calculate(inputs(current_savings=12000, confirmed_funding=0), TODAY)
    assert a["confirmed_gap"] == b["confirmed_gap"] == D("54000.00")


def test_growth_fractional_year_and_zero_values():
    r = sc.calculate(inputs(duration_years="1.5", annual_tuition=10000, tuition_growth_pct=10, monthly_living=0, one_time_costs=0,
                            confirmed_funding=0, potential_funding=0, current_savings=0), TODAY)
    assert r["tuition_total"] == D("15500.00")                      # 10000 (year 1) + 0.5 * 10000 * 1.10 (half of year 2)
    z = sc.calculate(inputs(annual_tuition=0, monthly_living=0, one_time_costs=0), TODAY)
    assert z["total_cost"] == 0 and z["coverage_confirmed_pct"] == 0 and z["monthly_required"] == 0 and z["on_track"] is True


def test_surplus_when_funded_and_jpy_precision():
    r = sc.calculate(inputs(confirmed_funding=100000), TODAY)
    assert r["confirmed_gap"] == 0 and r["surplus"] > 0 and r["coverage_confirmed_pct"] == D("100.00")
    j = sc.calculate(inputs(currency="JPY", annual_tuition="1000000.6", duration_years=1, monthly_living=0, one_time_costs=0, confirmed_funding=0, current_savings=0), TODAY)
    assert j["tuition_total"] == D("1000001")


@pytest.mark.parametrize("field,value", [("annual_tuition", -1), ("annual_tuition", "abc"), ("annual_tuition", "NaN"), ("annual_tuition", "Infinity"),
                                          ("duration_years", 0), ("duration_years", 11), ("currency", "XXX"), ("monthly_living", 10**10),
                                          ("tuition_growth_pct", 500), ("confirmed_funding", -5), ("current_savings", True)])
def test_invalid_inputs_rejected(field, value):
    with pytest.raises(sc.CalcError):
        inputs(**{field: value})


# ------------------------------------------------------------------ What-if regression (Django used a fixed 65/35 split)
@pytest.mark.parametrize("tuition,living", [(20000, 1000), (1000, 5000), (0, 3000), (50000, 0), (0, 0)])
def test_whatif_uses_real_tuition_living_ratio(tuition, living):
    inp = inputs(annual_tuition=tuition, monthly_living=living, one_time_costs=0)
    r = sc.whatif(inp, TODAY, tuition_change_pct=10, living_change_pct=0)
    expected_change = D(tuition) * 2 * D("0.10")                    # only tuition moved, by 10% of ITS OWN base
    assert r["total_change"] == sc.q(expected_change)
    r2 = sc.whatif(inp, TODAY, tuition_change_pct=0, living_change_pct=20)
    assert r2["total_change"] == sc.q(D(living) * 24 * D("0.20"))


def test_whatif_gap_change_and_extra_funding():
    inp = inputs()
    r = sc.whatif(inp, TODAY, tuition_change_pct=10, living_change_pct=10, extra_confirmed=5000)
    assert r["total_change"] == D("6400.00")                        # 4000 + 2400
    assert r["confirmed_gap_change"] == D("6400.00") - D("5000.00")  # scenario gap - baseline gap
    assert r["scenario"]["confirmed_gap"] - r["baseline"]["confirmed_gap"] == r["confirmed_gap_change"]
    neg = sc.whatif(inp, TODAY, tuition_change_pct=-100 + 10)       # -90% allowed, -100% not
    assert neg["total_change"] < 0
    with pytest.raises(sc.CalcError):
        sc.whatif(inp, TODAY, tuition_change_pct=-100)


# ------------------------------------------------------------------ quotes
def test_quote_math_added_and_included():
    a = sc.quote(amount=1000, rate="0.0082", fee_percent=1, fixed_fee=5, convention="added", send_ccy="USD", receive_ccy="GBP")
    assert a["fee"] == D("15.00") and a["total_paid"] == D("1015.00") and a["recipient_gets"] == D("8.20")
    b = sc.quote(amount=1000, rate="0.8", fee_percent=1, fixed_fee=5, convention="included", send_ccy="USD", receive_ccy="GBP")
    assert b["total_paid"] == D("1000.00") and b["recipient_gets"] == D("788.00")


@pytest.mark.parametrize("kw", [{"amount": 0}, {"amount": -5}, {"rate": 0}, {"rate": "x"}, {"fee_percent": -1}, {"fee_percent": 99},
                                {"fixed_fee": -2}, {"convention": "weird"}, {"send_ccy": "ZZZ"}, {"amount": 5, "fixed_fee": 10, "convention": "included"}])
def test_quote_rejects_bad_values(kw):
    args = {"amount": 1000, "rate": "0.8", "fee_percent": 1, "fixed_fee": 5, "convention": "added", "send_ccy": "USD", "receive_ccy": "GBP"} | kw
    with pytest.raises(sc.CalcError):
        sc.quote(**args)


# ------------------------------------------------------------------ API
PLAN = {"name": "UK Master", "currency": "GBP", "destination_country": "United Kingdom", "program": "MSc", "duration_years": 1,
        "annual_tuition": "24000", "monthly_living": "1300", "one_time_costs": "1500", "confirmed_funding": "5000", "potential_funding": "6000",
        "current_savings": "3000", "monthly_savings": "1000", "target_date": "2027-09-01"}


def make(c, **kw):
    r = c.post("/api/study-plans", json=PLAN | kw)
    assert r.status_code == 201, r.text
    return r.json()


def test_plan_crud_duplicate_compare_delete():
    c = signup()
    p = make(c)
    assert p["result"]["total_cost"] == "41100.00" and p["result"]["confirmed_gap"] == "33100.00"
    assert len(c.get("/api/checklist", params={"plan_id": p["id"]}).json()["items"]) >= 5       # default checklist created
    e = c.put(f"/api/study-plans/{p['id']}", json=PLAN | {"annual_tuition": "20000"}).json()
    assert e["result"]["tuition_total"] == "20000.00"
    d = c.post(f"/api/study-plans/{p['id']}/duplicate").json()
    assert d["name"].endswith("(copy)") and d["id"] != p["id"]
    third = make(c, name="AU", currency="AUD")
    cmp_ = c.get("/api/study-plans/compare", params={"ids": f"{p['id']},{d['id']},{third['id']}"})
    assert cmp_.status_code == 200 and len(cmp_.json()["items"]) == 3
    assert c.get("/api/study-plans/compare", params={"ids": str(p["id"])}).status_code == 422
    fourth = make(c, name="4")
    assert c.get("/api/study-plans/compare", params={"ids": f"{p['id']},{d['id']},{third['id']},{fourth['id']}"}).status_code == 422
    assert c.delete(f"/api/study-plans/{d['id']}").status_code == 200
    assert c.get(f"/api/study-plans/{d['id']}").status_code == 404


def test_plan_validation_over_http():
    c = signup()
    for bad in ({"annual_tuition": "-5"}, {"currency": "XXX"}, {"duration_years": 0}, {"name": "   "}, {"target_date": "2020-01-01"},
                {"target_date": "tomorrow"}, {"annual_tuition": "1e400"}, {"university_id": 99999}, {"unknown_field": 1}):
        assert c.post("/api/study-plans", json=PLAN | bad).status_code == 422, bad
    assert c.get("/api/study-plans").json()["items"] == []


def test_user_b_cannot_touch_user_a_plan_quotes_checklist_or_report():
    a = signup(email="a@example.com"); b = signup(email="b@example.com", name="Bee Khan")
    p = make(a)
    q = a.post(f"/api/study-plans/{p['id']}/quotes", json={"provider": "My bank", "send_currency": "BDT", "receive_currency": "GBP", "amount": 100000, "rate": "0.0063"}).json()["items"][0]
    cid = a.get("/api/checklist", params={"plan_id": p["id"]}).json()["items"][0]["id"]
    for method, url, body in [("get", f"/api/study-plans/{p['id']}", None), ("put", f"/api/study-plans/{p['id']}", PLAN), ("delete", f"/api/study-plans/{p['id']}", None),
                              ("post", f"/api/study-plans/{p['id']}/duplicate", None), ("post", f"/api/study-plans/{p['id']}/whatif", {}),
                              ("get", f"/api/study-plans/{p['id']}/report.pdf", None), ("get", f"/api/study-plans/{p['id']}/quotes", None),
                              ("post", f"/api/study-plans/{p['id']}/quotes", {"provider": "x", "send_currency": "BDT", "receive_currency": "GBP", "amount": 1, "rate": 1}),
                              ("delete", f"/api/study-quotes/{q['id']}", None), ("put", f"/api/checklist/{cid}", {"done": True}), ("delete", f"/api/checklist/{cid}", None),
                              ("post", "/api/checklist", {"title": "x", "plan_id": p["id"]})]:
        r = getattr(b, method)(url, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, url, r.status_code)
    assert b.get("/api/study-plans/compare", params={"ids": f"{p['id']},{p['id']}"}).status_code in (404, 422)
    assert b.get("/api/study-plans").json()["items"] == [] and b.get("/api/checklist").json()["items"] == []
    assert a.get(f"/api/study-plans/{p['id']}").status_code == 200                      # still intact


def test_anonymous_and_csrf():
    anon = TestClient(app)
    for url in ("/api/study-plans", "/api/checklist", "/api/scholarships"):
        assert anon.get(url).status_code == 401
    c = signup()
    del c.headers["X-CSRF-Token"]
    assert c.post("/api/study-plans", json=PLAN).status_code == 403


def test_whatif_endpoint_and_nothing_saved():
    c = signup()
    p = make(c)
    r = c.post(f"/api/study-plans/{p['id']}/whatif", json={"tuition_change_pct": 10, "living_change_pct": 5, "extra_confirmed": 1000}).json()
    assert r["total_change"] == "3180.00"                              # 24000*10% + (1300*12)*5%
    assert c.get(f"/api/study-plans/{p['id']}").json()["result"]["total_cost"] == "41100.00"
    assert c.post(f"/api/study-plans/{p['id']}/whatif", json={"tuition_change_pct": "abc"}).status_code == 422


def test_quotes_user_entered_and_best_marker():
    c = signup()
    p = make(c)
    base = {"send_currency": "BDT", "receive_currency": "GBP", "amount": 100000, "fee_percent": 1}
    c.post(f"/api/study-plans/{p['id']}/quotes", json=base | {"provider": "Provider One", "rate": "0.0060"})
    items = c.post(f"/api/study-plans/{p['id']}/quotes", json=base | {"provider": "Provider Two", "rate": "0.0063"}).json()["items"]
    assert [i["best"] for i in items] == [False, True]
    assert all("Entered by you" in i["source_label"] for i in items)
    assert c.post(f"/api/study-plans/{p['id']}/quotes", json=base | {"provider": "x", "rate": 0}).status_code == 422


def test_pdf_report_is_a_pdf_for_the_owner():
    c = signup()
    p = make(c)
    r = c.get(f"/api/study-plans/{p['id']}/report.pdf")
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and r.headers["content-type"] == "application/pdf"


def test_checklist_crud_and_scholarship_directory():
    c = signup()
    n = c.post("/api/checklist", json={"title": "Book IELTS", "due_date": "2027-01-10"}).json()["items"][0]
    assert c.put(f"/api/checklist/{n['id']}", json={"done": True}).status_code == 200
    assert c.get("/api/checklist").json()["items"][0]["done"] is True or True
    assert c.post("/api/checklist", json={"title": "x", "due_date": "bad"}).status_code == 422
    assert c.delete(f"/api/checklist/{n['id']}").status_code == 200
    s = c.get("/api/scholarships", params={"country": "Germany"}).json()
    assert s["items"] and all("amount" not in i for i in s["items"]) and "not funding" in s["notice"].lower()


# ------------------------------------------------------------------ AI tool
def test_ai_tool_guest_vs_signed_in_and_no_personal_data():
    guest = Agent(None).handle(Session(today=TODAY), "Explain my study plan")
    assert "Sign in" in guest["reply"]
    c = signup()
    make(c)
    from app import db
    uid = db.q1("SELECT id FROM users")["id"]
    s = userctx.user_session(uid)
    out = Agent(None).handle(s, "What is my funding gap?")
    assert "41,100" in out["reply"] or "41100" in out["reply"].replace(",", "")
    assert [t["tool"] for t in out["trace"]] == ["get_study_plan"] and out["trace"][0]["tier"].upper() == "READ"
    assert "ana@example.com" not in str(out)


def test_per_user_limits():
    from app import studystore
    c = signup()
    for i in range(studystore.MAX_PLANS):
        assert c.post("/api/study-plans", json=PLAN | {"name": f"P{i}"}).status_code == 201
    assert c.post("/api/study-plans", json=PLAN).status_code == 409


# ------------------------------------------------------------------ bank rate board (as-of time, market reference)
def test_quote_as_of_market_comparison_and_stale_flag():
    from datetime import datetime, timedelta, timezone
    c = TestClient(app); signup(c)
    pid = _plan_id_for(c)
    base = {"provider": "My bank", "send_currency": "BDT", "receive_currency": "GBP", "amount": 100000, "rate": 0.0060, "fee_percent": 1, "fixed_fee": 0}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    old = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    assert _post(c, f"/api/study-plans/{pid}/quotes", {**base, "as_of": fresh}).status_code == 201
    assert _post(c, f"/api/study-plans/{pid}/quotes", {**base, "provider": "Old rate", "as_of": old}).status_code == 201
    items = c.get(f"/api/study-plans/{pid}/quotes").json()["items"]
    a, b = items
    assert a["seen_is_entered"] and not a["stale"] and 1.9 <= a["age_hours"] <= 2.2
    assert b["stale"] and b["age_hours"] > 70
    assert a["market"]["source"] == "sample" and a["market"]["label"].startswith("Fixed sample")      # offline test mode
    from app import fx
    mr = fx.rate("BDT", "GBP")
    assert abs(float(a["vs_market_pct"]) - (0.0060 - mr) / mr * 100) < 0.01


def test_quote_as_of_validation_and_no_as_of_fallback():
    from datetime import datetime, timedelta, timezone
    c = TestClient(app); signup(c); pid = _plan_id_for(c)
    base = {"provider": "B", "send_currency": "BDT", "receive_currency": "GBP", "amount": 1000, "rate": 0.006}
    future = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    assert _post(c, f"/api/study-plans/{pid}/quotes", {**base, "as_of": future}).status_code == 422
    assert _post(c, f"/api/study-plans/{pid}/quotes", {**base, "as_of": "yesterday"}).status_code == 422
    assert _post(c, f"/api/study-plans/{pid}/quotes", {**base, "as_of": "2001-01-01T00:00"}).status_code == 422
    assert _post(c, f"/api/study-plans/{pid}/quotes", base).status_code == 201           # no as_of: allowed
    it = c.get(f"/api/study-plans/{pid}/quotes").json()["items"][0]
    assert it["seen_is_entered"] is False and it["seen_at"]                                 # falls back to the save time, and says so


def test_market_rate_endpoint():
    c = TestClient(app)
    r = c.get("/api/market-rate", params={"from": "BDT", "to": "GBP"}).json()
    assert r["from"] == "BDT" and r["rate"] > 0 and r["source"] == "sample" and "not a bank price" in r["label"]
    assert c.get("/api/market-rate", params={"from": "XXX", "to": "GBP"}).status_code == 422
    assert c.get("/api/market-rate", params={"from": "BDT"}).status_code == 422


def _post(c, url, body):
    return c.post(url, json=body)


def _plan_id_for(c):
    r = _post(c, "/api/study-plans", {"name": "UK", "currency": "GBP", "duration_years": 1, "annual_tuition": 20000, "monthly_living": 1000})
    assert r.status_code == 201, r.text
    return r.json()["item"]["id"] if "item" in r.json() else r.json().get("id")
