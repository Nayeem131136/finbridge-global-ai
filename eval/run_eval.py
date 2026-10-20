"""Run the FinBridge task-completion scenarios against the deterministic planner.

Usage:  python eval/run_eval.py                 # rule planner, writes eval/report.md
        python eval/run_eval.py --llm [--delay 4]  # same scenarios through the LLM chosen by env vars
                                                   # (GROQ_API_KEY), writes eval/report_llm.md
        python eval/run_eval.py --json          # machine-readable output
"""
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent import Agent          # noqa: E402
from app.llm import build_planner    # noqa: E402
from app.session import Session      # noqa: E402

SCENARIOS = json.loads((Path(__file__).parent / "scenarios.json").read_text())
TODAY = date(2026, 10, 12)


def _check(exp: dict, out: dict | None, s: Session, res: dict | None) -> list[str]:
    errs = []
    if out is not None:
        reply = out["reply"].lower()
        tools = [t["tool"] for t in out["trace"]]
        cards = [c["type"] for c in out["cards"]]
        for t in exp.get("tools_include", []):
            if t not in tools: errs.append(f"expected tool {t}, got {tools}")
        for t in exp.get("tools_exclude", []):
            if t in tools: errs.append(f"tool {t} must not run")
        for c in exp.get("cards_include", []):
            if c not in cards: errs.append(f"expected card {c}, got {cards}")
        for c in exp.get("cards_exclude", []):
            if c in cards: errs.append(f"card {c} must not appear")
        for w in exp.get("contains", []):
            if w.lower() not in reply: errs.append(f"reply missing '{w}'")
        for w in exp.get("not_contains", []):
            if w.lower() in reply: errs.append(f"reply must not contain '{w}'")
        for f in exp.get("flags_include", []):
            if f not in [x["type"] for x in out["flags"]]: errs.append(f"expected flag {f}")
        if "pending" in exp and bool(out["pending"]) != exp["pending"]:
            errs.append(f"pending should be {exp['pending']}")
        if "pending_warning_contains" in exp:
            w = " ".join((out["pending"] or {}).get("warnings", []))
            if exp["pending_warning_contains"].lower() not in w.lower(): errs.append("missing pending warning")
    if res is not None and "ok" in exp and res["ok"] != exp["ok"]:
        errs.append(f"confirm ok should be {exp['ok']}, got {res}")
    for cur, v in exp.get("balance_lt", {}).items():
        if not s.balances[cur] < v: errs.append(f"{cur} balance should be < {v}")
    for cur, v in exp.get("balance_eq", {}).items():
        if s.balances[cur] != v: errs.append(f"{cur} balance should be {v}, is {s.balances[cur]}")
    raw = json.dumps(s.audit.entries)
    for w in exp.get("audit_not_contains", []):
        if w in raw: errs.append(f"audit log leaks '{w}'")
    if "audit_valid" in exp and s.audit.verify()["ok"] != exp["audit_valid"]:
        errs.append(f"audit validity should be {exp['audit_valid']}")
    return errs


def run_scenario(sc: dict, agent: Agent | None = None) -> dict:
    agent = agent or Agent()
    s = Session(today=TODAY)
    s.balances.update(sc.get("setup", {}).get("balances", {}))
    last_token, errs = None, []
    for i, step in enumerate(sc["steps"], 1):
        out = res = None
        if "say" in step:
            out = agent.handle(s, step["say"])
            if out["pending"]:
                last_token = out["pending"]["token"]
        elif "confirm" in step:
            res = s.confirm(last_token or "none", step["confirm"])
        elif step.get("tamper"):
            if s.audit.entries:
                s.audit.entries[0]["detail"] = {"tampered": True}
        errs += [f"step {i}: {e}" for e in _check(step.get("expect", {}), out, s, res)]
    return {"id": sc["id"], "category": sc["category"], "title": sc["title"], "passed": not errs, "errors": errs}


def run_all(agent: Agent | None = None, delay: float = 0.0) -> list[dict]:
    import time
    out = []
    for sc in SCENARIOS:
        out.append(run_scenario(sc, agent))
        if delay:
            time.sleep(delay)      # stay under free-tier rate limits
    return out


def write_report(results: list[dict], planner_label: str = "deterministic rule planner (offline)",
                 filename: str = "report.md") -> str:
    total, passed = len(results), sum(r["passed"] for r in results)
    by_cat = defaultdict(lambda: [0, 0])
    for r in results:
        by_cat[r["category"]][1] += 1
        by_cat[r["category"]][0] += r["passed"]
    lines = ["# FinBridge evaluation report", "",
             "Planner: deterministic rule planner (offline). Data: illustrative sandbox rates and providers.", "",
             f"**Task completion: {passed}/{total} scenarios passed ({passed / total * 100:.0f}%).**", "",
             "| Category | Passed | Total |", "|---|---|---|"]
    lines += [f"| {c} | {p} | {t} |" for c, (p, t) in sorted(by_cat.items())]
    lines += ["", "## Scenarios", "", "| ID | Scenario | Result |", "|---|---|---|"]
    for r in results:
        lines.append(f"| {r['id']} | {r['title']} | {'PASS' if r['passed'] else 'FAIL: ' + '; '.join(r['errors'])} |")
    text = "\n".join(lines) + "\n"
    (Path(__file__).parent / filename).write_text(text)
    return text


if __name__ == "__main__":
    if "--llm" in sys.argv:
        planner = build_planner()
        if planner is None:
            sys.exit("No LLM key found. Set GROQ_API_KEY in backend/.env.")
        delay = float(sys.argv[sys.argv.index("--delay") + 1]) if "--delay" in sys.argv else 0.0
        results = run_all(Agent(planner), delay)
        d = planner.describe()
        print(write_report(results, f"LLM {d['provider']} / {d['model']}", "report_llm.md"))
        sys.exit(0)
    results = run_all()
    if "--json" in sys.argv:
        print(json.dumps(results, indent=1))
    else:
        print(write_report(results))
    sys.exit(0 if all(r["passed"] for r in results) else 1)
