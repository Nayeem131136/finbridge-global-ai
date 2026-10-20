# Architecture

```
Browser (frontend/)  --HTTP-->  FastAPI (main.py)
                                   |
                              Agent.handle()
                       injection scan -> planner -> tools
                         |                 |         |
                   rule planner       Groq tool    run_tool(): validate args,
                   (offline)          use (llm.py)   check tier, execute, audit
                                                        |
        fx / remit / budget / tuition / credit / invoice (pure functions, tested)
                                                        |
                         Session: quotes, pending transfers, sandbox balances, audit log
```

## Key design decisions

1. **One tool layer, two planners.** The Groq planner and the rule planner call the same tools through `run_tool()`, so the safety guarantees do not depend on which brain is active. The rule planner makes the demo work offline and makes the evaluation reproducible.
2. **The agent cannot move money.** `request_transfer` (tier EXECUTE) only creates a pending confirmation. `Session.confirm()` is reached only through `POST /api/confirm`, which the human triggers with a PIN. There is no tool that calls it.
3. **Quotes are server-side.** `compare_remittance_routes` stores each quote under an ID (`Q1`...). `request_transfer` takes only that ID, so the model can never invent or alter an amount.
4. **Invoices are data, not instructions.** `invoice.py` parses with regexes. Text in an invoice that tries to instruct an AI is flagged and ignored.
5. **Tamper-evident audit.** Every message, tool call and result is appended to a SHA-256 hash chain with PII masked at write time. `GET /api/audit` also returns chain verification.

## Tools and tiers

| Tool | Tier | Purpose |
|---|---|---|
| get_fx_rate, fx_timing, get_account, compare_remittance_routes | READ | lookups and comparisons |
| build_budget, plan_tuition, credit_roadmap, check_invoice | SUGGEST | advice and checks, no side effects |
| request_transfer | EXECUTE | prepare a transfer; human PIN required |

## Cost model (remit.py)

`fee = max(min_fee, fixed + pct * amount)`, `receive = (send - fee) * mid_rate * (1 - spread)`. For "recipient must receive X" the sender amount is solved iteratively so the recipient gets exactly X. Total cost = fee + spread cost, shown in the sender's currency and as a percentage. Ranking: cheapest, fastest, or balanced (`cost% + 0.15 * days`).

## Moving from sandbox to production

- Replace `data.USD_RATES` and `PROVIDERS` with live FX and provider quote APIs.
- Replace the in-memory sandbox account with a bank or wallet API using OAuth and a real step-up authentication (bank app, passkey) instead of a fixed PIN.
- Move SQLite to PostgreSQL (the SQL is plain; `db.py` is the only module that touches the driver) and run several workers behind a shared rate-limiter/session store.
- Full list: `docs/PRODUCTION_CHECKLIST.md`.

## Accounts, persistence and request flow (added in v3)

```
Browser (ES modules) --cookie fb_session (HttpOnly) + X-CSRF-Token--> FastAPI
   main.py   security-headers middleware, restricted CORS, generic error handler, /api/chat /confirm /wallet ...
   api_user.py  /api/auth/*  /api/profile  /api/universities  /api/budgets  /api/tuition-plans  /api/comparisons
                /api/records  /api/notifications  /api/dashboard  /api/invoice/extract
   userctx.py   resolve(): valid cookie => user Session (hydrated from DB); else anonymous guest Session (memory only)
   auth.py      scrypt hashing, sessions (only SHA-256 of the token stored), rate limiting, password reset tokens
   store.py     every private query filters by user_id (isolation); comparisons are recomputed on the server
   db.py        sqlite3, WAL, foreign keys ON, SQL migrations (backend/migrations/NNN_*.sql, table schema_migrations)
```

* **Identity is never taken from the request body.** The user id comes from the session cookie; guessing another user's row id returns 404.
* **Money-moving confirmation** (`/api/confirm`, `/api/wallet/withdraw`) uses `Session._check_secret`: account password for signed-in users, the public dev-only demo PIN for guests. Tokens are single-use, bound to the session, expire after 5 minutes; three wrong secrets lock the session for 5 minutes.
* **Persistence:** wallet balances, sandbox transfer/deposit/withdraw records and the hash-chained audit log are saved per user, so they survive a restart.
* **AI privacy:** `llm.system_for(session)` adds only home currency, study country and university name. Name, email, balances and saved plans are never sent.
* **Reminders:** `store.refresh_reminders` creates in-app notifications with a unique `dedupe_key`, so repeated page loads never duplicate them. No push/email channel exists; SMTP is used only for password-reset mail.

### Schema (migration 001)
users · auth_sessions · password_resets · universities · profiles · budgets · tuition_plans · comparisons · wallet_balances · sandbox_records · notifications · audit_events. Foreign keys cascade on user deletion; unique constraints: users.email, universities(name,country), sandbox_records.ref, notifications(user_id,dedupe_key); indexes on every user_id.
