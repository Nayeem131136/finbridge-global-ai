import json
from datetime import date

import httpx
import pytest

from app import fx
from app.agent import Agent
from app.data import USD_RATES
from app.llm import DEFAULT_MODEL, OpenAICompatPlanner, build_planner, _tools
from app.session import Session
from app.tools import BudgetArgs


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def S():
    return Session(today=date(2026, 10, 12))


# ------------------------------------------------------------------ schemas
def test_all_tool_schemas_are_portable():
    for t in _tools():
        raw = json.dumps(t["parameters"])
        for bad in ("$ref", "$defs", "anyOf", "title", "default", "additionalProperties", "exclusiveMinimum", "pattern"):
            assert bad not in raw, (t["name"], bad)
        assert t["parameters"]["type"] == "object"


def test_budget_args_accept_dict_and_list():
    a = BudgetArgs(monthly_income=1000, expenses={"rent": 300, "food": 200})
    b = BudgetArgs(monthly_income=1000, expenses=[{"category": "rent", "amount": 300}])
    assert a.expenses[0].category == "rent" and b.expenses[0].amount == 300


# ------------------------------------------------------------------ groq (OpenAI-compatible)
def test_groq_request_shape_and_tool_loop():
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append((req.headers["authorization"], req.headers.get("user-agent"), str(req.url), body))
        if len(seen) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "get_fx_rate",
                 "arguments": json.dumps({"from_currency": "USD", "to_currency": "BDT", "amount": 100})}}]}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "100 USD is 12,200 BDT."}}]})

    p = OpenAICompatPlanner("K", "some-model", http=client(handler))
    assert p.state == "untested"
    out = Agent(p).handle(S(), "convert please")
    assert out["reply"].startswith("100 USD") and out["cards"][0]["type"] == "fx_rate" and p.state == "ok"
    assert seen[0][2] == "https://api.groq.com/openai/v1/chat/completions" and seen[0][0] == "Bearer K"
    assert seen[0][1] == "FinBridge/1.0"
    assert seen[1][3]["messages"][-1]["role"] == "tool" and seen[1][3]["messages"][-1]["tool_call_id"] == "c1"


def test_groq_bad_tool_json_is_handled():
    n = {"i": 0}

    def handler(req):
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
                {"id": "c1", "function": {"name": "get_fx_rate", "arguments": "{not json"}}]}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "Sorry, retrying."}}]})

    out = Agent(OpenAICompatPlanner("K", "m", http=client(handler))).handle(S(), "convert")
    assert out["reply"] == "Sorry, retrying."


def test_groq_retries_once_on_429():
    n = {"i": 0}

    def handler(req):
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    out = Agent(OpenAICompatPlanner("K", "m", http=client(handler), retry_delay=0)).handle(S(), "hello there")
    assert out["reply"] == "ok" and n["i"] == 2


def test_groq_invalid_key_falls_back_and_reports_error():
    def handler(req):
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    p = OpenAICompatPlanner("bad", "m", http=client(handler), retry_delay=0)
    s = S()
    out = Agent(p).handle(s, "What is 100 USD in BDT?")
    assert out["mode"] == "rules" and "12,200" in out["reply"]
    assert p.state == "error" and "401" in p.last_error and "Invalid API Key" in p.last_error and "bad" not in p.last_error.replace("Invalid", "")
    assert any(e["kind"] == "llm_error" for e in s.audit.entries)


def test_groq_server_error_and_timeout_fall_back():
    def boom(req):
        return httpx.Response(500, json={"error": {"message": "down"}})

    def slow(req):
        raise httpx.ReadTimeout("timed out")

    for h in (boom, slow):
        p = OpenAICompatPlanner("K", "m", http=client(h), retry_delay=0)
        out = Agent(p).handle(S(), "What is 100 USD in BDT?")
        assert out["mode"] == "rules" and p.state == "error"


def test_groq_model_removed_error_is_visible():
    def handler(req):
        return httpx.Response(400, json={"error": {"message": "The model `x` has been decommissioned"}})

    p = OpenAICompatPlanner("K", "x", http=client(handler))
    Agent(p).handle(S(), "What is 100 USD in BDT?")
    assert "decommissioned" in p.last_error


def test_groq_no_choices_is_error():
    p = OpenAICompatPlanner("K", "m", http=client(lambda r: httpx.Response(200, json={"error": "x"})))
    out = Agent(p).handle(S(), "What is 100 USD in BDT?")
    assert out["mode"] == "rules" and p.state == "error"


# ------------------------------------------------------------------ selection
def _clean(monkeypatch):
    for k in ("GROQ_API_KEY", "FINBRIDGE_MODEL", "GROQ_MODEL", "GROQ_BASE_URL", "FINBRIDGE_OFFLINE", "FINBRIDGE_PROVIDER"):
        monkeypatch.delenv(k, raising=False)


def test_build_planner_groq_default_and_custom_model(monkeypatch):
    _clean(monkeypatch)
    assert build_planner() is None                                   # no key: rule engine
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    p = build_planner()
    assert p.name == "groq" and p.model == DEFAULT_MODEL and p.base_url == "https://api.groq.com/openai/v1"
    monkeypatch.setenv("FINBRIDGE_MODEL", "other-model")
    assert build_planner().model == "other-model"


def test_other_providers_are_ignored(monkeypatch):
    _clean(monkeypatch)
    for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(k, "x")
    assert build_planner() is None


def test_placeholder_key_is_not_used(monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "PASTE_YOUR_GROQ_KEY_HERE")
    assert build_planner() is None


def test_offline_switch_forces_rules(monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setenv("FINBRIDGE_OFFLINE", "1")
    assert build_planner() is None


def test_env_file_fills_empty_variable(tmp_path, monkeypatch):
    from app import envfile
    f = tmp_path / ".env"
    f.write_text("export GROQ_API_KEY=\"gsk_from_file\"\n")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.chdir(tmp_path)
    envfile.load()
    import os
    assert os.environ["GROQ_API_KEY"] == "gsk_from_file"
    monkeypatch.delenv("GROQ_API_KEY")


def test_health_and_llm_check_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    h = c.get("/api/health").json()
    assert h["mode"] == "rules" and h["llm_state"] == "none"
    p = OpenAICompatPlanner("K", "m", http=client(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})))
    monkeypatch.setattr(main.agent, "llm", p)
    main._LAST_PROBE[0] = 0
    r = c.post("/api/llm/check").json()
    assert r["ok"] and c.get("/api/health").json()["llm_state"] == "ok"
    p.http = client(lambda r: httpx.Response(401, json={"error": {"message": "Invalid API Key"}}))
    main._LAST_PROBE[0] = 0
    r = c.post("/api/llm/check").json()
    assert not r["ok"] and "401" in r["error"]
    assert c.get("/api/health").json()["llm_state"] == "error"
    main._LAST_PROBE[0] = 0
    monkeypatch.setattr(main.agent, "llm", None)
    assert c.post("/api/llm/check").json()["state"] == "none"


# ------------------------------------------------------------------ live fx
def test_live_fx_refresh_and_fallback(monkeypatch):
    saved = dict(USD_RATES)
    try:
        live = {c: v * 1.01 for c, v in saved.items()}
        ok = fx.refresh_live(http=client(lambda r: httpx.Response(200, json={"result": "success", "rates": live})), url="http://x")
        assert ok and fx.SOURCE == "live" and abs(USD_RATES["BDT"] - saved["BDT"] * 1.01) < 1e-9
        assert "open.er-api.com" in fx.source_label()
        # an incomplete or failing answer must not change anything
        before = dict(USD_RATES)
        assert not fx.refresh_live(http=client(lambda r: httpx.Response(200, json={"result": "success", "rates": {"USD": 1}})), url="http://x")
        assert not fx.refresh_live(http=client(lambda r: httpx.Response(500)), url="http://x")
        assert USD_RATES == before
    finally:
        USD_RATES.update(saved)
        fx.SOURCE = "sandbox"


def test_unavailable_default_model_is_replaced_automatically():
    used = []

    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "whisper-large-v3"}, {"id": "openai/gpt-oss-20b"}, {"id": "llama-guard-4-12b"}]})
        body = json.loads(req.content)
        used.append(body["model"])
        if body["model"] == DEFAULT_MODEL:
            return httpx.Response(404, json={"error": {"message": f"The model `{DEFAULT_MODEL}` does not exist or you do not have access to it."}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    p = OpenAICompatPlanner("K", DEFAULT_MODEL, http=client(handler)); p.auto_model = True
    out = Agent(p).handle(S(), "hello there")
    assert out["mode"] == "llm" and out["reply"] == "ok" and p.model == "openai/gpt-oss-20b" and p.state == "ok"
    assert used == [DEFAULT_MODEL, "openai/gpt-oss-20b"]


def test_explicit_model_is_never_replaced():
    def handler(req):
        return httpx.Response(404, json={"error": {"message": "The model `mine` does not exist"}})

    p = OpenAICompatPlanner("K", "mine", http=client(handler))      # auto_model False
    out = Agent(p).handle(S(), "What is 100 USD in BDT?")
    assert out["mode"] == "rules" and p.model == "mine" and "does not exist" in p.last_error


def test_ping_recovers_and_pick_model_skips_non_chat():
    from app.llm import pick_model
    assert pick_model(["whisper-large-v3", "llama-guard-4", "llama-3.1-8b-instant"]) == "llama-3.1-8b-instant"
    assert pick_model(["whisper-large-v3"]) is None
    assert pick_model(["x/custom-llama-big", "playai-tts"]) == "x/custom-llama-big"


def test_timezone_validation_without_system_database(monkeypatch):
    from app import api_user
    monkeypatch.setattr(api_user, "_TZ", None)
    monkeypatch.setattr(api_user, "available_timezones", lambda: set())     # what Windows without tzdata reports
    assert api_user.ProfileIn(timezone="Asia/Dhaka").timezone == "Asia/Dhaka"
    with pytest.raises(Exception):
        api_user.ProfileIn(timezone="not a zone!!")
