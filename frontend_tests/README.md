# Browser end-to-end tests (Playwright, Python)

These are the scripts I used to verify the UI in headless Chromium. They are **not** part of `pytest`.

```powershell
pip install playwright ; python -m playwright install chromium ; npm i axe-core@4.10.2   # axe only for script 5
# fresh server + empty DB for each script (port 8010):
cd backend
$env:FINBRIDGE_OFFLINE="1"; $env:FINBRIDGE_DB="$env:TEMP\e2e.db"; Remove-Item $env:FINBRIDGE_DB -ErrorAction SilentlyContinue
python -m uvicorn app.main:app --port 8010 *> ..\frontend_tests\server.log
# in another terminal, from frontend_tests:
python 1_main_journey.py        # signup, profile, plans, compare+save, wallet, password-confirmed transfer, reload, Bangla, mobile, logout/login, guest
python 2_reset_upload_delete.py # validation, forgot/reset password (reads link from server.log), PDF invoice upload, delete account
python 3_guest_demo.py          # guest one-click demo end to end
python 4_edit_delete_wallet_session.py  # budget/tuition edit+delete, reminder prefs, wallet validation, expired session
python 5_accessibility_axe.py   # axe-core WCAG A/AA scan
python 6_study_journey.py       # study plan create/what-if/quotes/checklist/PDF/compare/Bangla/mobile
python 7_globe_route_ratebord.py  # profile countries drive the globe route; unknown country; no page errors
```
Scripts 1, 2 and 4 each create their own users, so restart with a fresh DB between runs. Script 1 prints one expected 400 (deliberate wrong password).
