# Production readiness checklist

Status: **local demo / competition prototype. Not production-ready.** Items marked ☐ are not done.

## Done in this repository
- ✅ Password hashing (scrypt), HttpOnly/SameSite session cookie, Secure flag when `FINBRIDGE_ENV=production`, CSRF tokens, login rate limiting, session expiry
- ✅ Security headers, restricted CORS, generic 500 handler, API docs hidden in production
- ✅ Migrations, FK/unique constraints, per-user isolation, account deletion
- ✅ Secrets only via environment / git-ignored `.env`; `.env.example` provided

## Required before real users or real money
- ☐ Replace sandbox payments with a licensed provider/bank API; real KYC/AML, sanctions screening, Bangladesh Bank outward-remittance rules, legal review of terms and privacy policy
- ☐ Replace the guest demo PIN and password step-up with passkey / bank-app / OTP step-up; remove the demo PIN entirely
- ☐ Use a vetted identity provider or add email verification, MFA, breach-password checks, account lockout alerts
- ☐ PostgreSQL (or managed SQL) with backups, encryption at rest, retention policy; Alembic-style migration tooling
- ☐ Shared stores (Redis) for rate limiting and sessions; run behind a reverse proxy with TLS (set `FINBRIDGE_ENV=production`, `FINBRIDGE_CORS=https://your.domain`)
- ☐ Real notification provider (email/SMS/push) with unsubscribe handling; configure SMTP for password reset
- ☐ Central logging/monitoring/alerting, dependency scanning, SAST/DAST, penetration test
- ☐ Image-invoice OCR with malware scanning of uploads; profile image upload with content validation
- ☐ Load testing; accessibility audit (WCAG 2.2 AA) with real assistive-technology testing
- ☐ Data-protection compliance (consent records, export/erase workflows, DPA with the AI provider)

## Pre-deployment commands
```bash
pip install -r backend/requirements.txt
cd backend && python -m pytest -q          # must be all green
FINBRIDGE_ENV=production FINBRIDGE_CORS=https://your.domain python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```
(One worker only: rate limiter and session cache are in-memory.)
