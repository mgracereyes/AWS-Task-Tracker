-- Migration 001: business unit on users (Assignments and Admin screens, Nov 2026 mockups).
-- Run after schema.sql (v1.3). Safe to run twice.
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS business_unit VARCHAR(20) NOT NULL DEFAULT 'Dev C';
COMMENT ON COLUMN users.business_unit IS 'Business unit, e.g. Dev A, Dev C, DX, S OJT, Admin';
COMMIT;
