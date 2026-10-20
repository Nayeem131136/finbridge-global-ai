-- FinBridge Global AI schema v2: study planning (ported from the Django project, same database as accounts)
CREATE TABLE study_plans (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  destination_country TEXT,
  university_id    INTEGER REFERENCES universities(id),
  university_other TEXT,
  program          TEXT,
  currency         TEXT NOT NULL,
  duration_years   TEXT NOT NULL,                 -- Decimal stored as text: no float rounding
  annual_tuition   TEXT NOT NULL,
  monthly_living   TEXT NOT NULL,
  one_time_costs   TEXT NOT NULL DEFAULT '0',
  confirmed_funding TEXT NOT NULL DEFAULT '0',
  potential_funding TEXT NOT NULL DEFAULT '0',
  current_savings  TEXT NOT NULL DEFAULT '0',
  monthly_savings  TEXT NOT NULL DEFAULT '0',
  tuition_growth_pct TEXT NOT NULL DEFAULT '0',
  living_growth_pct  TEXT NOT NULL DEFAULT '0',
  target_date      TEXT,
  notes            TEXT,
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_study_plans_user ON study_plans(user_id);
CREATE TABLE plan_quotes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  plan_id       INTEGER NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
  provider      TEXT NOT NULL,                    -- label typed by the user, e.g. "Bank X (from their website)"
  send_currency TEXT NOT NULL,
  receive_currency TEXT NOT NULL,
  amount        TEXT NOT NULL,
  rate          TEXT NOT NULL,
  fee_percent   TEXT NOT NULL DEFAULT '0',
  fixed_fee     TEXT NOT NULL DEFAULT '0',
  convention    TEXT NOT NULL DEFAULT 'added' CHECK (convention IN ('added','included')),
  delivery_days TEXT,
  source        TEXT NOT NULL DEFAULT 'user_entered',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_plan_quotes_plan ON plan_quotes(plan_id);
CREATE TABLE checklist_items (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  plan_id   INTEGER REFERENCES study_plans(id) ON DELETE CASCADE,
  title     TEXT NOT NULL,
  due_date  TEXT,
  done      INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_checklist_user ON checklist_items(user_id);
CREATE TABLE scholarships (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  name     TEXT NOT NULL UNIQUE,
  provider TEXT NOT NULL,
  destination TEXT NOT NULL,                      -- country name or 'Multiple'
  level    TEXT,
  url      TEXT,
  note     TEXT NOT NULL DEFAULT 'Directory entry only. Eligibility, amounts and deadlines are NOT included: verify on the official site.'
);
