-- When the user saw this rate on the bank/provider's own page (optional; falls back to created_at).
ALTER TABLE plan_quotes ADD COLUMN as_of TEXT;
