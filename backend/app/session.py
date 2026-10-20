"""Per-session state and the simulated bank account (sandbox only; no real money)."""
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import date

from . import fx
from .data import BENEFICIARIES, DEFAULT_BALANCES, MAX_DEPOSIT_USD, SANDBOX_PIN, SINGLE_LIMIT_USD
from .security import AuditLog, compliance_check

PENDING_TTL = 300  # seconds


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    today: date = field(default_factory=date.today)
    balances: dict = field(default_factory=lambda: dict(DEFAULT_BALANCES))
    history: list = field(default_factory=list)          # [{role, content}] text only
    audit: AuditLog = field(default_factory=AuditLog)
    quotes: dict = field(default_factory=dict)
    pending: dict = field(default_factory=dict)
    transactions: list = field(default_factory=list)
    pin_attempts: int = 0
    lang: str = "en"
    pin: str = SANDBOX_PIN                  # DEVELOPMENT-ONLY public demo PIN, used by guest sessions only
    uid: int | None = None                  # database user id when signed in
    verifier: object = None                 # signed-in users re-enter their account password (callable str -> bool)
    context: dict = field(default_factory=dict)   # minimal profile hints for the AI (no name, email or amounts)
    persist_state: dict = field(default_factory=lambda: {"tx": 0, "ledger": 0, "audit": 0})
    locked_until: float = 0.0
    ledger: list = field(default_factory=list)   # deposits and withdrawals (separate from transfers)
    _quote_n: int = 0

    # ---- quotes (server-side, so the agent can never invent an amount)
    def save_quote(self, quote: dict, purpose: str) -> str:
        self._quote_n += 1
        qid = f"Q{self._quote_n}"
        self.quotes[qid] = {**quote, "purpose": purpose, "created": time.time()}
        return qid

    @property
    def sent_today_usd(self) -> float:
        return sum(t["usd"] for t in self.transactions)

    # ---- transfer lifecycle
    def request_transfer(self, quote_id: str, beneficiary: str, country: str) -> dict:
        q = self.quotes.get(quote_id)
        if not q:
            raise ValueError(f"Unknown quote '{quote_id}'. Run a route comparison first.")
        if time.time() - q["created"] > 900:
            raise ValueError("This quote expired. Please compare routes again.")
        usd = fx.convert(q["send_amount"], q["send_currency"], "USD")
        check = compliance_check(amount_usd=usd, purpose=q["purpose"], country=country,
                                 recent_usd=[t["usd"] for t in self.transactions],
                                 sent_today_usd=self.sent_today_usd)
        if self.balances.get(q["send_currency"], 0) < q["send_amount"]:
            check["allowed"] = False
            check["reasons"].append(f"Insufficient {q['send_currency']} balance in the sandbox account.")
        known = beneficiary in BENEFICIARIES
        if not known:
            check["warnings"].append("New beneficiary: verify the name and account with the recipient before confirming.")
        if not check["allowed"]:
            return {"status": "blocked", "compliance": check}
        token = secrets.token_urlsafe(12)
        self.pending[token] = {"quote_id": quote_id, "beneficiary": beneficiary, "country": country,
                               "usd": usd, "expires": time.time() + PENDING_TTL}
        return {"status": "pending_confirmation", "token": token, "compliance": check,
                "verified_beneficiary": known, "expires_in": PENDING_TTL}

    def confirm(self, token: str, pin: str) -> dict:
        p = self.pending.get(token)
        if not p:
            return {"ok": False, "error": "No such pending transfer (it may have been used or cancelled)."}
        if time.time() > p["expires"]:
            del self.pending[token]
            return {"ok": False, "error": "Confirmation window expired. Please start again."}
        err = self._check_secret(pin, "transfers")
        if err:
            return {"ok": False, "error": err}
        q = self.quotes[p["quote_id"]]
        # re-check compliance at execution time
        check = compliance_check(amount_usd=p["usd"], purpose=q["purpose"], country=p["country"],
                                 recent_usd=[t["usd"] for t in self.transactions],
                                 sent_today_usd=self.sent_today_usd)
        if not check["allowed"] or self.balances.get(q["send_currency"], 0) < q["send_amount"]:
            del self.pending[token]
            return {"ok": False, "error": "Compliance re-check failed: " + "; ".join(check["reasons"] or ["insufficient balance"])}
        del self.pending[token]
        self.balances[q["send_currency"]] -= q["send_amount"]
        tx = {"ref": "SBX-" + uuid.uuid4().hex[:8].upper(), "provider": q["provider"],
              "send": q["send_amount"], "send_currency": q["send_currency"],
              "receive": q["receive_amount"], "receive_currency": q["receive_currency"],
              "beneficiary": p["beneficiary"], "purpose": q["purpose"], "usd": p["usd"], "status": "completed (sandbox)"}
        self.transactions.append(tx)
        return {"ok": True, "transaction": tx, "balances": dict(self.balances)}

    # ---- money in / out (human-only actions; the AI has no tool for these)
    def _verify(self, secret: str) -> bool:
        if self.verifier is not None:
            return bool(self.verifier(str(secret)))
        return secrets.compare_digest(str(secret), self.pin)

    def _check_secret(self, secret: str, what: str) -> str | None:
        """Guests confirm with the demo PIN; signed-in users re-enter their password. 3 misses lock for 5 minutes."""
        label = "password" if self.verifier is not None else "PIN"
        if time.time() < self.locked_until:
            return f"Too many wrong {label} attempts. Session locked for {what}."
        if not self._verify(secret):
            self.pin_attempts += 1
            if self.pin_attempts >= 3:
                self.pin_attempts, self.locked_until = 0, time.time() + 300
                return f"Wrong {label}. Too many wrong {label} attempts. Session locked for {what} for 5 minutes."
            return f"Wrong {label}. {3 - self.pin_attempts} attempt(s) left."
        self.pin_attempts = 0
        return None

    def deposit(self, amount: float, currency: str, source: str) -> dict:
        currency = fx.norm(currency)
        if not (0 < amount) or fx.convert(amount, currency, "USD") > MAX_DEPOSIT_USD:
            return {"ok": False, "error": f"Deposit must be above 0 and at most {MAX_DEPOSIT_USD:,.0f} USD equivalent."}
        self.balances[currency] = self.balances.get(currency, 0.0) + amount
        entry = {"ref": "DEP-" + uuid.uuid4().hex[:8].upper(), "type": "deposit", "amount": amount,
                 "currency": currency, "via": source, "status": "completed (sandbox)"}
        self.ledger.append(entry)
        return {"ok": True, "entry": entry, "balances": dict(self.balances)}

    def withdraw(self, amount: float, currency: str, pin: str) -> dict:
        currency = fx.norm(currency)
        err = self._check_secret(pin, "money movement")
        if err:
            return {"ok": False, "error": err}
        usd = fx.convert(amount, currency, "USD") if amount > 0 else 0
        if not (0 < amount) or usd > SINGLE_LIMIT_USD:
            return {"ok": False, "error": f"Withdrawal must be above 0 and at most {SINGLE_LIMIT_USD:,.0f} USD equivalent."}
        if self.balances.get(currency, 0.0) < amount:
            return {"ok": False, "error": f"Insufficient {currency} balance."}
        self.balances[currency] -= amount
        entry = {"ref": "WDR-" + uuid.uuid4().hex[:8].upper(), "type": "withdrawal", "amount": amount,
                 "currency": currency, "via": "your linked bank account (simulated)", "status": "completed (sandbox)"}
        self.ledger.append(entry)
        return {"ok": True, "entry": entry, "balances": dict(self.balances)}

    def cancel(self, token: str) -> bool:
        return self.pending.pop(token, None) is not None
