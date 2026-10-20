# Known limitations (honest list)

* **No real money, no real provider quotes.** Transfers are simulated. Transfer-route comparison uses fictional sample providers; study-plan quotes are typed by the user.
* **Live services not verified in the build environment:** Live Groq calls, live exchange rates, SMTP. Run `python backend/check_llm.py` yourself; it prints `[OK]` only after a real tool-calling request succeeds.
* **Bank rates are typed by you:** no bank has an open rate API here, so FinBridge does not fetch real bank-by-bank rates. It shows the time you entered, flags rates older than 24 h, and compares with a market reference rate. That reference is live only when the server can reach open.er-api.com (not verified in the build sandbox); otherwise a fixed sample is used and labelled.
* **Globe countries:** the home→study route works for 18 countries in a built-in list (capital or main city); others are not drawn.
* **Data is illustrative:** universities and scholarships are directory entries without amounts, eligibility or deadlines.
* **Not ported from Django:** profile photo upload.
* **Not implemented:** image-invoice OCR, PostgreSQL, email/SMS/push reminders (in-app only), MFA/email verification.
* **Single process:** rate limiter, session cache and guest sessions are in memory; run one worker.
* **Language:** UI is English/Bangla; most server messages are English; free-text Bangla chat needs an AI key.
* **Currencies:** 12 supported currencies; plans use one currency and are never auto-converted; FX sensitivity is educational, not a forecast.
* **Not advice:** all outputs are estimates from user input; not financial, legal or immigration advice; no compliance certification (KYC/AML/sanctions are simulated).
* **Evaluation:** the 36 scenarios are self-authored regression tests, not an independent benchmark.
* **Bank rates are typed by you:** FinBridge does not fetch real bank-by-bank rates. It shows the time you entered, flags rates older than 24 h and compares with a market reference rate. That reference is live only when the server can reach open.er-api.com (not verified in our offline build environment); otherwise a fixed sample is used and labelled.
* **Globe countries:** the home to study country route works for 18 countries in a built-in list; others are not drawn.
