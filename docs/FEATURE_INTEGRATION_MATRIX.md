# Feature integration matrix

Status: ✅ implemented and tested (automated) · 🟡 partial · ❌ not available

| Feature | From | Status | Where / how tested |
|---|---|---|---|
| Register / login / logout / reset password / delete account | A | ✅ | `test_accounts.py`, Playwright 1, 2 |
| Persistent profile (countries, currency, university, language) | A+B | ✅ | profile dialog; `test_accounts.py` |
| Study plan: tuition, living, one-time, confirmed funding, potential scholarships, savings, target date | B | ✅ | `studycalc.py`; `test_study.py` (exact-number tests) |
| Confirmed gap vs potential gap, coverage %, monthly saving needed | B | ✅ | `test_exact_totals_gaps_and_monthly`, `test_potential_funding_never_counts_as_confirmed` |
| What-if lab (fixed) | B | ✅ | `test_whatif_*` with unusual tuition/living ratios |
| FX sensitivity ±5/±10% | B | ✅ (educational) | `studycalc.sensitivity` |
| Create / edit / duplicate / delete plan; compare up to 3 | B | ✅ | `test_plan_crud_duplicate_compare_delete`, Playwright 6 |
| User-entered bank/provider rates with as-of time, stale flag, market comparison | B | ✅ | `test_quote_*`, `test_market_rate_endpoint` (no live bank prices) |
| Globe route from profile home → study country | A+B | ✅ | `frontend_tests/7_globe_route_ratebord.py` |
| Illustrative route comparison (fictional providers) | A | ✅ labelled sample | existing tests |
| AI agent explains plan (tool `get_study_plan`) | A | ✅ rule engine tested; 🟡 live LLM unverified here | `test_ai_tool_*` |
| Groq AI provider (only provider; Gemini/OpenRouter/Claude removed) | A | 🟡 mocked-HTTP tests only (success, 401, 429, 500, timeout, bad JSON); live call needs your key | `check_llm.py`, status button |
| Invoice fraud indicators (text/PDF) | A | ✅ | existing tests |
| Human-confirmed simulated transfer, audit chain, tamper demo | A | ✅ | existing tests, Playwright 1 |
| Checklist (default items, add/toggle/delete) | B | ✅ | `test_checklist_*` |
| Scholarship directory (names + official links only) | B | ✅ listing, ❌ amounts/eligibility on purpose | `test_checklist_crud_and_scholarship_directory` |
| PDF report | B | ✅ | `test_pdf_report_*`, Playwright 6 |
| Dashboard (home), budgets, tuition savings plans, reminders (in-app) | A | ✅ | Playwright 1, 4 |
| EN / Bangla UI | A | ✅ UI, 🟡 server messages mostly English | Playwright 1, 6 |
| 3D globe with fallback | A+B | ✅ | `body.no-webgl` fallback |
| Profile photo upload | B | ❌ not ported | KNOWN_LIMITATIONS |
| Image OCR for invoices | – | ❌ | KNOWN_LIMITATIONS |
| Real money movement / real provider quotes / KYC | – | ❌ by design | KNOWN_LIMITATIONS |

| User-entered bank/provider rates with as-of time, stale flag, market comparison; globe route from profile countries | B | done | `test_quote_*`, `test_market_rate_endpoint`, `frontend_tests/7_globe_route_ratebord.py` |
