# Baseline audit (both projects, before integration)

Method: I unzipped both projects and read/ran the actual code. Nothing below is copied from earlier AI summaries. No secret values appear here.

## Commands executed and results
| Project | Command | Result |
|---|---|---|
| A FastAPI | `cd backend && python -m pytest -q` | 121 passed |
| A FastAPI | `python eval/run_eval.py` | 36/36 scenarios passed (offline rule engine) |
| A FastAPI | Playwright scripts in `frontend_tests/` (headless Chromium) | all journeys passed, no page errors |
| B Django | `python manage.py check` (as delivered) | **FAILED**: `CSRF_TRUSTED_ORIGINS` was `True` in `.env` (must be URLs) |
| B Django | same, after deleting that one `.env` line | no issues |
| B Django | `python manage.py test` (after the fix) | 9 passed |
| B Django | `migrate`, `seed_demo`, then GET of 12 pages as the demo user | all HTTP 200 |

Not verifiable here (no internet in the build sandbox): live Groq calls, live FX (open.er-api.com), SMTP.

## Project B (Django) findings
| # | Finding | Severity | Status in the integrated project |
|---|---|---|---|
| B2 | `.env` contained `CSRF_TRUSTED_ORIGINS=True`, which makes `manage.py check` fail | High (blocks start) | Not applicable to the new project |
| B3 | What-if Lab (client-side JS) assumed tuition = 65% and living = 35% of the total | High (wrong numbers) | **Fixed**: server-side `studycalc.whatif`, scales the plan's real values; regression tests with unusual ratios |
| B4 | `AUTH_PASSWORD_VALIDATORS = []` (any password accepted) | Medium | Password policy enforced in the new auth (10+ chars, letter+digit, not common) |
| B5 | Public demo account with a documented password | Medium (demo only) | New project has no default account; guests use a clearly labelled demo mode |
| B6 | Groq adapter used the default Python User-Agent and hid the provider's error text; a Cloudflare 403 can look like "bad key" | Medium | The new LLM layer uses an OpenAI-compatible client with proper headers, a real error path and a `check_llm.py` command |
| B7 | Savings entered in two places (profile and plan) with two different gap formulas | Medium | One definition: savings counted once, in the plan (see FEATURE_GUIDE) |
| B8 | Templates stored as single minified lines | Low | Frontend rewritten as readable modules |
| B9 | Photo upload, payments quote pages and other views were not audited line by line | Unknown | Profile photo upload is **not** ported (documented limitation) |

## Project A (FastAPI) findings
| # | Finding | Status |
|---|---|---|
| A1 | No study-planning features (funding gap, what-if, checklist, scholarships, PDF) | Ported (see matrix) |
| A2 | Sandbox/demo PIN `1234` for guests | Kept, labelled development-only; signed-in users must use their password |
| A3 | In-memory rate limiter and session cache (single process) | Documented limitation |
| A4 | No image OCR, no PostgreSQL | Documented limitation |

## Duplicate features and integration risks
* Both projects have accounts, plans, budgets/plans dashboard, a checklist-like flow and an AI coach. The integrated product keeps A's accounts/AI/payment code (stronger security) and ports B's planning features to it.
* Risk: two databases/two auth systems. Avoided by porting instead of running both servers.
* Risk: formulas duplicated. Avoided: `studycalc.py` is the single source of truth; the UI and the AI only display its output.
