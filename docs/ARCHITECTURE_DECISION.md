# Architecture decision: one FastAPI application

**Decision.** Keep Project A (FastAPI + SQLite + vanilla ES-module frontend) as the only backend. Port Project B's study-planning features into it. Do **not** run Django alongside it.

**Why**
1. A already has the harder, higher-scoring parts: tool-calling agent, human confirmation, audit chain, accounts, CSRF, rate limits, 121 tests.
2. B's value is its domain logic (cost/gap/what-if/checklist/scholarships/PDF). That is a few hundred lines and ports cleanly.
3. One service = one database, one login, one deployment, one thing to explain in five minutes. Two services would need shared auth, an API contract, startup ordering and failure handling for no user benefit.

**Trade-offs accepted.** Django's admin site, ORM and form handling are not used. Profile photo upload (Django `ImageField`) is not ported.

**Service boundaries (single service).**
* `studycalc.py`: the only place study-cost formulas exist (Decimal).
* `studystore.py`: persistence, every query filtered by `user_id`.
* `api_study.py`: HTTP layer + validation + PDF.
* `tools.py: get_study_plan`: READ-only tool so the AI can *explain* server-calculated numbers; it cannot change plans or move money.
* Database: one SQLite file, migrations `001` (accounts etc.), `002` (study planning) and `003` (time a rate was seen).

**Failure handling.** AI provider down or rate-limited → automatic fallback to the offline rule engine (the status pill says which mode is active). Calculations never depend on the AI.
