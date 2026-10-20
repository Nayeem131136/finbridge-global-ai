# Feature guide (for a non-technical student)

**1. Create an account** and fill in your profile (countries, currency, university, language).
**2. Study plan tab → New study plan.** Enter tuition per year, living cost per month, one-time costs (visa, flights, deposit), how long you will study, and the money you have.

Three kinds of money are kept separate:
* **Confirmed funding**: money you are sure about (family, approved loan, confirmed scholarship).
* **Current savings**: money you already hold.
* **Potential scholarships**: hoped-for money. It is shown separately and **never counted as confirmed**.

**Formulas** (all in `backend/app/studycalc.py`, exact decimal arithmetic):
```
total cost       = tuition + living + one-time          (growth % applied per academic year, last partial year pro-rated)
confirmed money  = confirmed funding + current savings   (savings counted once)
confirmed gap    = max(0, total - confirmed money)
potential gap    = max(0, confirmed gap - potential funding)
monthly needed   = confirmed gap / months until target date (12 if no date)
coverage %       = confirmed money / total
```
Rounding: half-up to 2 decimals (0 for JPY). One plan uses one currency; nothing is converted automatically.

**3. What-if lab**: change tuition or living cost by a percentage (applied to *your own* tuition and living values) or add extra funding. Nothing is saved.
**4. Bank and provider rate board**: type the rate and fees a bank/provider shows on its own website, **and the time you saw it**. FinBridge calculates what you pay and what arrives, marks the best value, shows how far each rate is below/above the **market reference rate** (live from open.er-api.com when online, otherwise a labelled fixed sample), and flags any rate older than 24 hours with "re-check". It never fetches bank prices itself: banks publish no open API, so you type them.

**4b. Globe route**: set Home country and Study country in your profile (or open a study plan) and the globe shows that route. Countries outside the 18 in the built-in list are ignored and the route is cleared.
**5. Checklist, scholarship directory (names and official links only), PDF report, compare up to 3 plans.**
**6. Assistant tab**: ask "Explain my study plan". The AI only explains the server's numbers. It cannot change them or move money.
**7. Simulated payments**: the assistant can *prepare* a sandbox transfer. You confirm with your account password. No real money moves.
**8. Invoice checker**: paste or upload a text PDF invoice. It lists suspicious signs. It is a risk indicator, not proof of fraud.

## Live vs sample data
| Item | Source |
|---|---|
| Study plan numbers, quotes you type | **your input** (nothing fetched) |
| Route comparison providers/fees | **illustrative sample** (fictional providers) |
| Exchange rates | live (open.er-api.com) when online, otherwise fixed sample rates; the status panel says which |
| Universities, scholarships | **sample directory** (names/links only) |
| AI answers | live provider only when a key is configured and the call succeeds; otherwise the rule engine (labelled) |

## Bank and provider rate board, and globe route
Type the rate and fees a bank or provider shows on its own website, **and the time you saw it**. FinBridge calculates what you pay and what arrives, marks the best value, shows how far each rate is below or above the **market reference rate** (live from open.er-api.com when online, otherwise a labelled fixed sample), and flags any rate older than 24 hours with "re-check". It never fetches bank prices itself: banks publish no open API here, so you type them. Set Home country and Study country in your profile (or open a study plan) and the globe shows that route; countries outside the built-in list of 18 are ignored.
