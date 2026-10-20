# FinBridge Global AI — Technical Documentation

**Competition:** 2026 Shenzhen International FinTech Competition · International Track · Topic C  
**Team:** Md. Mahdi Hasan Nayeem (team lead, backend and security); Rupasha Khan Tandra (frontend and demonstration video)

## Overview
FinBridge Global AI is a competition prototype for students planning to study abroad. It combines study-cost planning, funding-gap analysis, payment-route comparison, invoice-risk indicators and an AI assistant. Transfers are simulated; the application does not move real money. Provider examples and fees are illustrative.

## Architecture
The submitted implementation uses one **FastAPI** service, **SQLite**, and a static **HTML/CSS/vanilla JavaScript** frontend. Groq is the only external AI provider. A deterministic rule planner is used when Groq is not configured or unavailable. Both planners share a validated tool-execution layer.

## Core capabilities
- Study plans: tuition, living and one-time costs; confirmed and potential funding; funding gap, coverage, monthly target, what-if scenarios, comparison, checklist and PDF report.
- Cross-border planning: illustrative route comparisons, user-entered quotes and FX timing information.
- Invoice risk indicators: text-PDF extraction, beneficiary comparison and suspicious-language checks. Results are not proof of fraud.
- AI assistant: allow-listed tools, argument validation, fallback behaviour and status that reports live AI only after a real successful provider request.
- Accounts: authentication, session expiry, CSRF controls, user-scoped data and account deletion.

## Study-cost formulas
- Total cost = tuition + living costs + one-time costs.
- Confirmed funds = confirmed funding + current savings.
- Confirmed gap = max(0, total cost − confirmed funds).
- Potential gap = max(0, confirmed gap − potential funding).
- Monthly target = confirmed gap divided by months until the target date.

Potential funding is kept separate from confirmed funds; savings are counted once; calculations use Python `Decimal`.

## Security boundaries
Password hashing, session token hashing, CSRF protection, user-scoped queries, input validation, PDF signature/size checks, transfer confirmation, single-use confirmation tokens, prompt-injection handling, masked audit events and environment-based secrets are covered by application tests. This is not an independent security audit or certification.

## Verification status (19 October 2026)
- `cd backend && python -m pytest -q`: **171 passed** in this review environment.
- `python eval/run_eval.py`: **36/36 scenarios passed** using the offline rule planner. These are team-authored regression cases, not an independent benchmark.
- Live Groq: **not verified in this review**; run `python check_llm.py` from `backend/` with a valid key.
- Browser journeys: not rerun in this review because Playwright Chromium was unavailable.
- Live FX, SMTP, external security testing and load testing: not verified.

## Known limitations
This is a local competition prototype, not production-ready for real funds or customer data. Provider prices are illustrative; FX may use clearly labelled sample values; university and scholarship listings are not verified offers; invoice scanning/OCR is not supported; SQLite is not encrypted at rest; rate limiting and session cache are in memory; email verification and MFA are absent; SMTP is required for actual password-reset email delivery.

## Run locally
Requirements: Python 3.11+. From the project root use `run.bat` on Windows or follow `README.md`. Manually: enter `backend/`, create and activate a virtual environment, install `requirements.txt`, copy `.env.example` to `.env`, optionally set `GROQ_API_KEY`, then run `python -m uvicorn app.main:app --port 8000`. Open `http://localhost:8000`.

## Addendum: rate board and market rate
Migration `003` adds `plan_quotes.as_of` (when the user saw the rate). `GET /api/market-rate?from=&to=` returns the market reference rate and says whether it is live or a fixed sample. Typed rates older than 24 hours are flagged. The globe route comes from the profile's home and study country.
