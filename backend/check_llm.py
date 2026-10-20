"""Check your Groq setup with ONE real tool-calling request.

    Windows PowerShell:   cd backend ; py check_llm.py
    (reads GROQ_API_KEY and optional FINBRIDGE_MODEL from backend/.env or the environment)

Prints [OK] only if Groq really answered and the model called a FinBridge tool.
The key is sent only to api.groq.com and is never printed.
"""
import os
import sys
from datetime import date

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import envfile                                   # noqa: E402

envfile.load()
from app.agent import Agent                               # noqa: E402
from app.llm import DEFAULT_MODEL, GROQ_BASE, OpenAICompatPlanner, _real_key, pick_model   # noqa: E402
from app.session import Session                           # noqa: E402


def main() -> int:
    key = _real_key(os.getenv("GROQ_API_KEY"))
    if not key:
        print("[FAIL] GROQ_API_KEY is missing (or still the placeholder). Put it in backend/.env as GROQ_API_KEY=gsk_...")
        return 1
    chosen = (os.getenv("FINBRIDGE_MODEL") or os.getenv("GROQ_MODEL") or "").strip()
    model = chosen or DEFAULT_MODEL
    base = os.getenv("GROQ_BASE_URL") or GROQ_BASE
    print(f"Key found (length {len(key)}), model: {model}")
    try:
        r = httpx.get(base.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key}", "User-Agent": "FinBridge/1.0"}, timeout=30)
    except httpx.HTTPError as e:
        print(f"[FAIL] Cannot reach Groq: {type(e).__name__}: {e}"); return 1
    print(f"Model list: HTTP {r.status_code}")
    if r.status_code == 401:
        print("[FAIL] Groq rejected the key (401). Create a new key at console.groq.com and update backend/.env."); return 1
    if r.status_code == 200:
        ids = sorted(m.get("id", "") for m in r.json().get("data", []))
        print(f"{len(ids)} models visible: {', '.join(ids)}")
        if model not in ids:
            alt = pick_model(ids)
            print(f"[WARN] '{model}' is not available to your key." + (f" The app will use '{alt}' automatically." if (alt and not chosen) else " Set FINBRIDGE_MODEL=<one of the ids above that supports tools>."))
            if alt and not chosen:
                model = alt
    else:
        print(f"Body: {r.text[:200]}")
    s = Session(today=date(2026, 10, 12))
    planner = OpenAICompatPlanner(key, model, base)
    planner.auto_model = not chosen
    try:
        out = Agent(planner).handle(s, "What is the cheapest way to pay 1000 USD tuition from BDT?")
    except Exception as e:                                # noqa: BLE001
        print(f"[FAIL] {type(e).__name__}: {str(e)[:200]}"); return 2
    used = [t["tool"] for t in out["trace"]]
    if out["mode"] == "llm" and "compare_remittance_routes" in used:
        print(f"[OK] LIVE Groq tool calling works: model {planner.model}, tools used {used}"); return 0
    print(f"[WARN] mode={out['mode']} tools={used}. Groq error: {planner.last_error or 'none'} (the app fell back to the rule engine).")
    return 2


if __name__ == "__main__":
    sys.exit(main())
