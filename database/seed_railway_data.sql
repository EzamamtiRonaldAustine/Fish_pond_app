-- ============================================================================
-- Railway Database Seed Script
-- ============================================================================
-- This script inserts essential default data to ensure the API works for
-- the Raspberry Pi hardware agent (DEVICE_DB_ID=1).
-- ============================================================================

BEGIN;

-- 1. Ensure Default Organization exists
INSERT INTO organizations (id, name, subscription_tier, max_devices, is_active)
VALUES (1, 'Default Organization', 'basic', 5, TRUE)
ON CONFLICT (id) DO NOTHING;

-- 2. Link Admin User to Organization (if not already)
-- The admin user is created in init_railway_db.sql with organization_id 1
-- This is just a safety update.
UPDATE users SET organization_id = 1 WHERE username = 'admin' AND organization_id IS NULL;

-- 3. Ensure Default Device exists (ID 1)
-- This matches DEVICE_DB_ID=1 in pi/.env and pi/config.py
INSERT INTO devices (
    id, 
    device_id, 
    name, 
    description, 
    organization_id, 
    status, 
    health_status,
    created_at
)
VALUES (
    1, 
    'LEGACY-DEVICE-001', 
    'Main Pond Pi', 
    'Default hardware agent for monitoring', 
    1, 
    'active', 
    'healthy',
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- 4. Ensure Device Status row exists for ID 1
INSERT INTO device_status (
    device_id, 
    pump_running, 
    pump_mode, 
    led_status, 
    buzzer_active, 
    is_online, 
    network_ok, 
    thingspeak_ok, 
    api_ok, 
    updated_at
)
VALUES (
    1, 
    FALSE, 
    'OFF', 
    'GOOD', 
    FALSE, 
    FALSE, 
    TRUE, 
    TRUE, 
    TRUE, 
    NOW()
)
ON CONFLICT (device_id) DO NOTHING;

COMMIT;
