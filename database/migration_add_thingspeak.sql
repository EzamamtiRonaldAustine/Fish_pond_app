-- Migration script to add missing columns to device_status table
-- This fixes the error: column "thingspeak_ok" does not exist and other missing columns

ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS thingspeak_ok BOOLEAN NOT NULL DEFAULT TRUE;

-- Add other potentially missing columns from the full schema (Raspberry.sql)
ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS api_ok BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS thread_health JSONB NOT NULL DEFAULT '{}';

ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Also add buzzer_active if missing (used in the API queries)
ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS buzzer_active BOOLEAN NOT NULL DEFAULT FALSE;
