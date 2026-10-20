"""Sandbox reference data for FinBridge.

IMPORTANT: every rate, fee and provider below is ILLUSTRATIVE sandbox data.
They are not live quotes and the providers are fictional. Replace them with
real provider APIs in production (see docs/ARCHITECTURE.md).
"""

# Units of currency per 1 USD (illustrative snapshot)
USD_RATES = {
    "USD": 1.0, "BDT": 122.0, "CNY": 7.15, "MYR": 4.45, "GBP": 0.78,
    "EUR": 0.92, "AUD": 1.52, "CAD": 1.37, "JPY": 150.0, "SGD": 1.34,
    "INR": 83.5, "AED": 3.6725,
}

CURRENCY_ALIASES = {
    "usd": "USD", "dollar": "USD", "dollars": "USD", "bdt": "BDT", "taka": "BDT", "tk": "BDT",
    "cny": "CNY", "yuan": "CNY", "rmb": "CNY", "myr": "MYR", "ringgit": "MYR",
    "gbp": "GBP", "pound": "GBP", "pounds": "GBP", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "aud": "AUD", "cad": "CAD", "jpy": "JPY", "yen": "JPY", "sgd": "SGD",
    "inr": "INR", "rupee": "INR", "rupees": "INR", "aed": "AED", "dirham": "AED",
}
SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "৳": "BDT"}

# Fictional providers. fee = max(min_fee_usd, fixed_usd + pct% of amount)
PROVIDERS = [
    dict(id="bankwire", name="Bank Wire (SWIFT)", fixed_usd=25.0, pct=0.0, min_fee_usd=25.0,
         spread_pct=2.4, speed_hours=72, max_usd=50000, purposes=None, receive_ccy=None,
         note="Widest coverage; intermediary banks may add fees."),
    dict(id="flowremit", name="FlowRemit (online transfer)", fixed_usd=1.5, pct=0.4, min_fee_usd=3.0,
         spread_pct=0.7, speed_hours=24, max_usd=10000, purposes=None,
         receive_ccy={"USD", "GBP", "EUR", "AUD", "CAD", "CNY", "MYR", "SGD", "JPY", "AED"},
         note="Low spread, next-day delivery."),
    dict(id="swiftcash", name="SwiftCash (instant wallet)", fixed_usd=0.0, pct=1.2, min_fee_usd=2.0,
         spread_pct=1.6, speed_hours=1, max_usd=2500,
         purposes={"living", "rent", "family_support", "books", "other"},
         receive_ccy={"USD", "GBP", "EUR", "AUD", "CAD", "MYR", "SGD"},
         note="Near-instant, small amounts, not for tuition."),
    dict(id="unipay", name="UniPay (tuition specialist)", fixed_usd=8.0, pct=0.0, min_fee_usd=8.0,
         spread_pct=0.45, speed_hours=48, max_usd=60000, purposes={"tuition"},
         receive_ccy={"USD", "GBP", "EUR", "AUD", "CAD", "CNY", "MYR", "SGD"},
         note="Pays the university directly and gives a payment receipt."),
]

# Saved (verified) beneficiaries in the sandbox profile
BENEFICIARIES = {
    "Example University Bursar": {"account": "GB82 EXMP 0000 1234 5678 90", "country": "GB",
                                    "currency": "GBP", "kind": "university"},
    "Demo State University Bursar": {"account": "US64 DEMO 0000 2222 3333 44", "country": "US",
                                      "currency": "USD", "kind": "university"},
    "Sample Tech Institute Bursar": {"account": "AU12 SAMP 0000 5555 6666 77", "country": "AU",
                                      "currency": "AUD", "kind": "university"},
}
DEFAULT_UNIVERSITY = "Example University Bursar"
UNIVERSITIES = [k for k, v in BENEFICIARIES.items() if v["kind"] == "university"]
HOME_CURRENCIES = ["BDT", "INR", "USD", "GBP", "EUR", "AUD", "CAD", "MYR", "SGD", "JPY", "CNY", "AED"]
MAX_DEPOSIT_USD = 100000.0

DEFAULT_BALANCES = {"BDT": 900000.0, "USD": 1200.0}

ALLOWED_PURPOSES = {"tuition", "living", "rent", "family_support", "books", "insurance", "other"}
BLOCKED_COUNTRIES = {"KP", "IR", "SY", "CU"}   # mock sanctions list for the sandbox
SINGLE_LIMIT_USD = 10000.0
DAILY_LIMIT_USD = 15000.0
SANDBOX_PIN = "1234"

NEEDS = {"rent", "food", "utilities", "transport", "tuition", "health", "insurance", "phone",
         "internet", "books", "groceries"}
WANTS = {"entertainment", "shopping", "travel", "dining", "subscriptions", "other"}
