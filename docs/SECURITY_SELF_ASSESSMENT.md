# FinBridge Global AI — Security Self-Assessment

**Scope:** Team self-assessment of the submitted competition prototype. This is not an independent audit, penetration test, compliance certification or guarantee of security. All money movement is simulated.

## Assets
Accounts and credentials; private study plans, budgets and quotes; transfer confirmation; Groq API configuration; audit events; and uploaded invoice PDFs.

## Controls reviewed
- **Credentials and sessions:** scrypt password hashing with per-user salt; password policy; rate-limited login; random session token with only its hash stored; HttpOnly/SameSite cookie and session expiry.
- **CSRF and access control:** per-session CSRF token on state-changing requests; user-scoped queries; cross-user access tests for study-plan resources.
- **Input and database safety:** decimal/date validation, rejection of unknown fields, record caps, parameterized SQL, escaped search wildcards and safe text rendering.
- **Uploads:** PDF signature check, 2 MB cap, in-memory extraction, no execution or persistent storage. Text PDFs only.
- **AI boundaries:** registered tools, argument validation, READ/SUGGEST/EXECUTE permission tiers, untrusted tool-result handling, prompt-injection checks and human confirmation for simulated transfers.
- **Secrets and logs:** keys read from environment or `backend/.env`; `.env` is ignored by Git and excluded from the submission ZIP; audit fields mask identifiers. Never include the actual key in source, screenshots or documentation.
- **Browser protections:** security headers and restricted CORS are covered by tests.

## Compliance boundary
Simulated limits, sample restricted-country lists and beneficiary warnings are demonstrations only; they are not live KYC, AML or sanctions screening. Invoice warnings are risk indicators, not proof of fraud.

## Residual risks
1. Live Groq requests were not verified in this review; mocked HTTP tests do not prove real provider connectivity.
2. Live exchange-rate and SMTP paths were not verified.
3. In-memory sessions and rate limits require a single-process deployment; shared storage is needed for multi-worker deployment.
4. SQLite is not encrypted at rest.
5. Email verification and MFA are not implemented. Guest demo PIN is public and development-only.
6. No independent penetration test, load test or compliance review has been performed.

## Release guidance
The prototype is suitable for a controlled competition demonstration with synthetic data, subject to final live Groq and browser checks. Do not describe it as production-ready or independently audited. Run `python check_llm.py` from `backend/` with a valid key and verify the final package contains no `.env`, database files or secrets.
