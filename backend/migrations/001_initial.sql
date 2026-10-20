-- FinBridge schema v1 (plain SQL, portable to PostgreSQL with minor type changes)
CREATE TABLE users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  pw_salt       BLOB NOT NULL,
  pw_hash       TEXT NOT NULL,
  accepted_terms_at TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  last_login_at TEXT
);
CREATE TABLE auth_sessions (
  token_hash  TEXT PRIMARY KEY,                 -- sha256 of the cookie value; the raw token is never stored
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf        TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at  REAL NOT NULL
);
CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id);
CREATE TABLE password_resets (
  token_hash TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at REAL NOT NULL,
  used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE universities (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  name    TEXT NOT NULL,
  country TEXT NOT NULL,
  city    TEXT,
  source  TEXT NOT NULL DEFAULT 'sample directory (name and location only; not verified for payments)',
  UNIQUE(name, country)
);
CREATE INDEX idx_universities_country ON universities(country);
CREATE TABLE profiles (
  user_id          INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  home_country     TEXT,
  study_country    TEXT,
  language         TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en','bn')),
  currency         TEXT NOT NULL DEFAULT 'BDT',
  timezone         TEXT NOT NULL DEFAULT 'Asia/Dhaka',
  study_level      TEXT,
  university_id    INTEGER REFERENCES universities(id) ON DELETE SET NULL,
  university_other TEXT,
  program          TEXT,
  monthly_income   REAL,
  monthly_budget   REAL,
  tuition_date     TEXT,
  remind_tuition   INTEGER NOT NULL DEFAULT 1,
  remind_budget    INTEGER NOT NULL DEFAULT 1,
  remind_savings   INTEGER NOT NULL DEFAULT 1,
  updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE budgets (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  income     REAL NOT NULL,
  currency   TEXT NOT NULL,
  expenses   TEXT NOT NULL,                      -- JSON object {category: amount}
  target_pct REAL NOT NULL DEFAULT 20,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_budgets_user ON budgets(user_id);
CREATE TABLE tuition_plans (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  total           REAL NOT NULL,
  currency        TEXT NOT NULL,
  due_dates       TEXT NOT NULL,                 -- JSON array of ISO dates
  home_currency   TEXT NOT NULL,
  saved           REAL NOT NULL DEFAULT 0,
  monthly_saving  REAL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_tuition_user ON tuition_plans(user_id);
CREATE TABLE comparisons (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  label      TEXT NOT NULL,
  amount     REAL NOT NULL,
  from_ccy   TEXT NOT NULL,
  to_ccy     TEXT NOT NULL,
  purpose    TEXT NOT NULL,
  basis      TEXT NOT NULL,
  best       TEXT NOT NULL,                      -- name of the cheapest route when saved
  snapshot   TEXT NOT NULL,                      -- JSON of the quotes at save time (illustrative data)
  fx_source  TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_comparisons_user ON comparisons(user_id);
CREATE TABLE wallet_balances (
  user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  currency TEXT NOT NULL,
  amount   REAL NOT NULL,
  PRIMARY KEY (user_id, currency)
);
CREATE TABLE sandbox_records (                    -- sandbox transfers, deposits, withdrawals (never real money)
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ref        TEXT NOT NULL UNIQUE,
  kind       TEXT NOT NULL CHECK (kind IN ('transfer','deposit','withdrawal')),
  detail     TEXT NOT NULL,                      -- JSON
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_records_user ON sandbox_records(user_id, id);
CREATE TABLE notifications (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  dedupe_key TEXT NOT NULL,
  message    TEXT NOT NULL,
  due_on     TEXT,
  read       INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, dedupe_key)
);
CREATE TABLE audit_events (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  seq     INTEGER NOT NULL,
  body    TEXT NOT NULL,                         -- JSON of the full hash-chained entry
  PRIMARY KEY (user_id, seq)
);
