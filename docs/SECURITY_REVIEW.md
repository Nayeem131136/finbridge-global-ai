# Security review (not a certification)

Scope: the integrated FastAPI application. Manual code review plus automated tests; no external penetration test.

| Area | Finding / control | Evidence |
|---|---|---|
| Passwords | scrypt + per-user salt; policy 10+ chars, letter+digit, not common/email/name | `test_signup_*` |
| Sessions | random token (only SHA-256 stored), HttpOnly, SameSite=Lax, Secure in production, 12 h expiry | `test_session_expiry`, Playwright 1 |
| CSRF | `X-CSRF-Token` required on every state-changing request, including all study endpoints | `test_csrf_required_for_state_changes`, `test_anonymous_and_csrf` |
| Ownership (IDOR) | every study/quote/checklist/report query filters by the session user; other users get 404, never 403/200 | `test_user_b_cannot_touch_user_a_plan_quotes_checklist_or_report` (12 routes) |
| Input validation | Decimal parsing; NaN/Infinity/negative/huge/odd currencies rejected; unknown JSON fields rejected; dates validated; per-user caps (30 plans, 20 quotes/plan, 100 checklist items) | `test_invalid_inputs_rejected`, `test_plan_validation_over_http`, `test_per_user_limits` |
| Injection | parameterised SQL only; LIKE wildcards escaped; UI inserts text with `textContent` | code review, `test_university_search_and_filter` |
| Uploads | only PDF text extraction (magic bytes, 2 MB, in memory, never executed/stored) | `test_invoice_pdf_extraction_and_limits`, `test_upload_rejects_non_pdf_and_bad_base64` |
| Money movement | simulated only; confirmation token single-use, bound to session, password step-up, replay rejected, 3-miss lock | `test_accounts.py` |
| AI safety | allow-listed tools, validated arguments, tool output labelled untrusted, no tool can confirm a transfer; `get_study_plan` is READ and sends only the user's plan numbers when they ask about their plan (no name/email) | `test_ai_tool_*`, `test_llm.py` |
| AI abuse | chat endpoint rate-limited (30/min/session); provider calls have timeouts and one retry | `main.py`, `llm.py` |
| Headers / CORS | CSP, nosniff, X-Frame-Options DENY, no-store on API; CORS restricted to localhost unless configured | `test_security_headers_and_cors` |
| Rate board / market rate | rates are user-typed and labelled; "seen at" time must be valid, ≤1 day in the future, ≤365 days old; rates >24 h flagged; `/api/market-rate` accepts only supported currency codes, is read-only and needs no sign-in (public reference data), labelled live vs fixed sample | `test_quote_as_of_validation_and_no_as_of_fallback`, `test_quote_as_of_market_comparison_and_stale_flag`, `test_market_rate_endpoint` |
| Error leakage | generic 500 without stack traces | `test_unexpected_errors_do_not_leak_details` |
| Logs | audit log masks emails/account numbers; secrets never logged | `test_secrets_never_reach_the_audit_log` |

## Residual risks / manual checks still required
In-memory rate limiter and caches (single worker); SQLite not encrypted; no email verification or MFA; guest demo PIN is public by design; CSP allows inline styles; live provider and live market-rate behaviour unverified (the market-rate route is unauthenticated); no penetration test; HTTPS/HSTS depends on your deployment. See `PRODUCTION_CHECKLIST.md`.
