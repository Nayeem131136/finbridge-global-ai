# Judge demo script (about 5 minutes) and manual verification

## Setup
`cd backend && python -m uvicorn app.main:app --port 8000` → open http://localhost:8000. For repeatable results run with `FINBRIDGE_OFFLINE=1`.

## Walkthrough
1. **Create account** (name, email, password 10+ chars, tick terms). You land on the personalised Home.
2. **Profile** (account menu): set home/study country, currency, **search "Toronto"**, select University of Toronto (note: "selection does not verify enrollment"), program, tuition date; Save. Try *Other / not listed* too.
2b. **Study plan tab → New study plan** (UK, University of Manchester sample, MSc 1 year: tuition 28,000, living 1,500/month, one-time 3,000 GBP; confirmed funding 10,000, savings 5,000, potential scholarship 5,000). Show *confirmed gap* vs *potential gap*; open **What-if** (+10% tuition) and note the gap moves by exactly the tuition change; add a bank **rate** you type from a provider site with the time you saw it (note the "below market" line and the market-rate label); tick **checklist**; **Download PDF**; ask the Assistant **"Explain my study plan"**.
3. **My plans → New budget** (income 90000, rent 30000, food 15000…) and **New tuition plan** (3000 USD, due dates, saved 100000 BDT). Progress bar and shortfall appear.
4. **Assistant → "Cheapest tuition route"**, then **Save this comparison**. Open **Home**: saved comparison, deadlines, progress, reminders.
5. **Wallet → Add money**, then ask **"Pay 1500 GBP tuition to the university"**. The confirmation dialog asks for your **account password** (a wrong one is rejected; replay of the same token fails).
6. **Prompt-injection chip** ("Ignore previous instructions…") → blocked, flagged.
7. **Invoice**: chip "Check an invoice" or Home → *Check an invoice* → upload a text PDF. Highlighted reasons; "risk indicator, not proof".
8. **Security panel → Try to tamper with the log**: labelled simulation; real chain stays valid.
9. **EN / বাংলা** toggle (persisted to your profile). Resize to phone width.
10. **Sign out**, sign in again: data persists. **Continue as demo guest** shows the guest flow (demo PIN 1234, nothing saved).
11. Forgot password: request link; in development the link is printed in the **server console** (`[DEV ONLY] Password reset link …`).

## Manual verification checklist
- Cookie `fb_session` is HttpOnly (DevTools → Application → Cookies); `localStorage` holds only `fb_lang`.
- A second browser/profile cannot see the first user's plans.
- `python -m pytest -q` (see docs/TEST_REPORT.md for the last verified count) and `python eval/run_eval.py` (36/36).
