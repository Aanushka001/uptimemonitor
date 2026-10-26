ALTER TABLE monitors ADD COLUMN IF NOT EXISTS claimed_until timestamptz;

CREATE INDEX IF NOT EXISTS idx_monitors_due ON monitors (is_active, last_checked_at);