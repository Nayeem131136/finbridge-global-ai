# Verification Report

**Review date:** 19 October 2026  
**Environment:** Python 3.13; extracted submission package; offline rule planner.

| Check | Command | Result |
|---|---|---|
| Backend tests | `cd backend && python -m pytest -q` | **171 passed** in this review environment |
| Offline task scenarios | `python eval/run_eval.py` | **36/36 passed** |
| Browser journeys | Playwright scripts | Not rerun in this review; Chromium executable unavailable |
| Live Groq | `python check_llm.py` / app | Not verified by us (no internet in our build environment). The team leader reports that the AI answers on their own computer with a real key (19 Oct 2026; raw output not captured) |
| Live FX / SMTP | Connected-service checks | Not verified |
| External security / load testing | External assessment | Not performed |

The 36 scenarios are team-authored regression tests, not an independent benchmark. The mocked Groq tests cover representative provider responses but do not establish live API connectivity. Capture fresh output after running the browser scripts and `check_llm.py` on a connected machine. Do not include API keys or personal data in evidence.
