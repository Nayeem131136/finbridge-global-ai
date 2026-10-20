"""Security layer: injection scan, PII masking, hash-chained audit log, compliance checks."""
import hashlib
import json
import re
import time

from .data import ALLOWED_PURPOSES, BLOCKED_COUNTRIES, DAILY_LIMIT_USD, SINGLE_LIMIT_USD

# ---------------------------------------------------------------- injection
_INJECTION = [re.compile(p, re.I | re.S) for p in [
    r"ignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)",
    r"disregard\s.{0,40}(instructions|rules|policy|policies)",
    r"(reveal|show|print|repeat|leak)\b.{0,30}(system\s+prompt|your\s+instructions|api\s*key|secret)",
    r"\byou\s+are\s+now\b|\bact\s+as\s+(an?\s+)?(admin|root|developer|dan)\b",
    r"\b(skip|bypass|disable|without)\b.{0,25}\b(confirmation|confirm|pin|verification|kyc|limit|compliance)\b",
    r"\b(send|transfer|wire|drain)\b.{0,20}\b(all|everything|entire|whole)\b.{0,20}\b(funds|money|balance|savings|account)\b",
    r"developer\s+mode|jailbreak",
    r"</?\s*(system|assistant|tool|instructions?)\s*>",
]]


def injection_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for p in _INJECTION for m in p.finditer(text or "")]


def scan_injection(text: str) -> list[str]:
    return [p.pattern[:40] for p in _INJECTION if p.search(text or "")]


# ---------------------------------------------------------------- PII masking
_EMAIL = re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b")
_LONGNUM = re.compile(r"(?<![\d.,])\+?\d[\d\s-]{7,}\d(?![\d,])")


def mask_pii(text):
    if not isinstance(text, str):
        return text
    text = _EMAIL.sub(lambda m: f"{m[1]}***@{m[2]}", text)
    text = _IBAN.sub(lambda m: m[0][:4] + " **** " + m[0][-3:], text)
    text = _LONGNUM.sub(lambda m: "****" + re.sub(r"\D", "", m[0])[-3:], text)
    return text


def mask_obj(obj):
    if isinstance(obj, str):
        return mask_pii(obj)
    if isinstance(obj, dict):
        return {k: mask_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mask_obj(v) for v in obj]
    return obj


# ---------------------------------------------------------------- audit log
class AuditLog:
    """Append-only, hash-chained log. Editing any past entry breaks verify()."""

    def __init__(self):
        self.entries: list[dict] = []

    def append(self, kind: str, detail: dict) -> dict:
        prev = self.entries[-1]["hash"] if self.entries else "GENESIS"
        body = {"seq": len(self.entries) + 1, "ts": round(time.time(), 3), "kind": kind,
                "detail": mask_obj(detail), "prev": prev}
        body["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
        self.entries.append(body)
        return body

    def tamper_demo(self) -> dict:
        """Sandbox demo: edit one past entry in a COPY and show that verification catches it. The real log is untouched."""
        import copy
        if not self.entries:
            return {"ok": False, "error": "No actions logged yet. Ask the assistant something first."}
        clone = AuditLog()
        clone.entries = copy.deepcopy(self.entries)
        idx = len(clone.entries) // 2
        target = clone.entries[idx]
        before_detail = json.dumps(target["detail"], default=str)[:80]
        target["detail"] = {"edited": "attacker changed this entry"}
        return {"ok": True, "entry": target["seq"], "kind": target["kind"], "before": before_detail,
                "copy_result": clone.verify(), "real_result": self.verify()}

    def verify(self) -> dict:
        prev = "GENESIS"
        for e in self.entries:
            body = {k: v for k, v in e.items() if k != "hash"}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
            if e["prev"] != prev or digest != e["hash"]:
                return {"ok": False, "broken_at": e["seq"], "count": len(self.entries)}
            prev = e["hash"]
        return {"ok": True, "count": len(self.entries)}


# ---------------------------------------------------------------- compliance
def compliance_check(*, amount_usd: float, purpose: str, country: str, recent_usd: list[float],
                     sent_today_usd: float) -> dict:
    """Return {'allowed': bool, 'reasons': [...], 'warnings': [...]}"""
    reasons, warnings = [], []
    if purpose not in ALLOWED_PURPOSES:
        reasons.append(f"Purpose '{purpose}' is not an allowed transfer purpose.")
    if (country or "").upper() in BLOCKED_COUNTRIES:
        reasons.append("Destination country is restricted by the sanctions screening list.")
    if amount_usd > SINGLE_LIMIT_USD:
        reasons.append(f"Amount is above the {SINGLE_LIMIT_USD:,.0f} USD single-transfer limit and needs manual review by a human officer.")
    if sent_today_usd + amount_usd > DAILY_LIMIT_USD:
        reasons.append(f"This would exceed the {DAILY_LIMIT_USD:,.0f} USD daily limit.")
    near = [a for a in recent_usd[-3:] if 0.8 * SINGLE_LIMIT_USD <= a < SINGLE_LIMIT_USD]
    if len(near) >= 2 and 0.8 * SINGLE_LIMIT_USD <= amount_usd < SINGLE_LIMIT_USD:
        reasons.append("Repeated transfers just under the limit look like structuring and are blocked for review.")
    if amount_usd > 0.5 * SINGLE_LIMIT_USD:
        warnings.append("Large transfer: keep the receipt and invoice for your records.")
    return {"allowed": not reasons, "reasons": reasons, "warnings": warnings}
