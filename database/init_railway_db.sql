-- Railway Database Initialization Script
-- Run this once when setting up the PostgreSQL database on Railway

-- Apply schema in order
-- 1. Core tables (users, devices)
\i schema_v1.sql

-- 2. Organizations support  
\i schema_v2.sql

-- 3. Hardware control and status tables
\i Raspberry.sql

-- 4. Apply any missing column migrations
ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS thingspeak_ok BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS api_ok BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS thread_health JSONB NOT NULL DEFAULT '{}';

ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE device_status 
ADD COLUMN IF NOT EXISTS buzzer_active BOOLEAN NOT NULL DEFAULT FALSE;

-- Create initial admin user (password: admin123)
INSERT INTO users (email, password_hash) VALUES 
('admin@fishpond.com', 'pbkdf2:sha256:260000$salt$hash') 
ON CONFLICT (email) DO NOTHING;

-- Create test device
INSERT INTO devices (id, name, user_id) VALUES 
(1, 'Fish Pond Device 1', 1) 
ON CONFLICT (id) DO NOTHING;

COMMIT;
