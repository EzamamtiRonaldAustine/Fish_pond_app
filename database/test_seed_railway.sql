-- ============================================================================
-- Railway Test Data Seed
-- ============================================================================
-- Run this AFTER init_railway_db.sql has been applied.
-- Use: \i 'C:/Users/USER/Desktop/Fish_Pond_app/database/test_seed_railway.sql'
--
-- Adds: test device, sensor readings, alerts, pond_config, pump_log
-- Safe to run once; re-running will add duplicate rows (truncate first if needed).
-- ============================================================================

-- 1. Test device (org 1, created_by admin user 1)
INSERT INTO devices (
    device_id,
    name,
    description,
    organization_id,
    created_by,
    status,
    last_seen
)
VALUES (
    'POND-TEST-001',
    'Test Pond Device',
    'Demo device for sensor readings and alerts',
    1,
    1,
    'active',
    NOW()
)
ON CONFLICT (device_id) DO NOTHING;

-- 2. Sensor readings (8 rows) – GOOD, WARNING, CRITICAL progression
INSERT INTO sensor_readings (
    temperature,
    ph,
    ec,
    nitrogen,
    phosphorus,
    turbidity,
    quality_status,
    quality_score,
    timestamp,
    device_id
)
SELECT
    v.temperature,
    v.ph,
    v.ec,
    v.nitrogen,
    v.phosphorus,
    v.turbidity,
    v.quality_status,
    v.quality_score,
    v.ts,
    (SELECT id FROM devices WHERE device_id = 'POND-TEST-001' LIMIT 1)
FROM (VALUES
    (25.5, 7.2, 450.0, 5.3, 2.1, false, 'GOOD', 15, NOW() - INTERVAL '2 hours'),
    (25.8, 7.3, 455.0, 5.5, 2.2, false, 'GOOD', 16, NOW() - INTERVAL '90 minutes'),
    (26.1, 7.4, 460.0, 5.8, 2.3, false, 'GOOD', 18, NOW() - INTERVAL '1 hour'),
    (26.5, 7.6, 470.0, 6.0, 2.4, false, 'GOOD', 20, NOW() - INTERVAL '45 minutes'),
    (26.8, 7.8, 475.0, 6.2, 2.6, false, 'GOOD', 22, NOW() - INTERVAL '30 minutes'),
    (27.2, 8.0, 485.0, 6.5, 2.8, true, 'WARNING', 38, NOW() - INTERVAL '15 minutes'),
    (27.8, 8.5, 510.0, 7.0, 3.2, true, 'WARNING', 55, NOW() - INTERVAL '5 minutes'),
    (28.5, 8.9, 540.0, 7.8, 3.8, true, 'CRITICAL', 82, NOW())
) AS v(temperature, ph, ec, nitrogen, phosphorus, turbidity, quality_status, quality_score, ts);

-- 3. Alerts linked to sensor readings (6th, 7th, 8th readings = WARNING/CRITICAL)
-- Uses subqueries to resolve sensor_reading_id from the inserted rows
INSERT INTO alerts (alert_type, severity, message, sensor_reading_id, device_id, acknowledged, timestamp)
VALUES
    ('pH_HIGH', 'WARNING', 'pH level elevated: 8.0',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp ASC LIMIT 1 OFFSET 5),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), false, NOW() - INTERVAL '15 minutes'),
    ('TURBIDITY_HIGH', 'WARNING', 'Water is turbid',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp ASC LIMIT 1 OFFSET 5),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), true, NOW() - INTERVAL '14 minutes'),
    ('pH_HIGH', 'WARNING', 'pH level elevated: 8.5',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp ASC LIMIT 1 OFFSET 6),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), false, NOW() - INTERVAL '5 minutes'),
    ('TEMPERATURE_HIGH', 'WARNING', 'Temperature rising: 27.8°C',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp ASC LIMIT 1 OFFSET 6),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), false, NOW() - INTERVAL '5 minutes'),
    ('pH_CRITICAL', 'CRITICAL', 'pH dangerously high: 8.9',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp ASC LIMIT 1 OFFSET 7),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), false, NOW() - INTERVAL '1 minute'),
    ('TEMPERATURE_CRITICAL', 'CRITICAL', 'Temperature too high: 28.5°C',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp ASC LIMIT 1 OFFSET 7),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), false, NOW() - INTERVAL '1 minute'),
    ('TURBIDITY_CRITICAL', 'CRITICAL', 'Water extremely turbid',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp ASC LIMIT 1 OFFSET 7),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), false, NOW());

-- 4. Pond config (default settings)
INSERT INTO pond_config (config_key, config_value, description)
VALUES
    ('alert_email_enabled', 'true', 'Enable email alerts'),
    ('alert_sms_enabled', 'true', 'Enable SMS alerts'),
    ('data_retention_days', '90', 'Number of days to keep sensor readings'),
    ('pump_auto_mode', 'true', 'Enable automatic pump control'),
    ('dashboard_refresh_interval', '10', 'Dashboard refresh interval in seconds')
ON CONFLICT (config_key) DO NOTHING;

-- 5. Pump log (sample entries)
INSERT INTO pump_log (mode, duration_seconds, triggered_by, sensor_reading_id, device_id, timestamp)
VALUES
    ('SHORT', 60, 'AUTOMATIC',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp DESC LIMIT 1),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), NOW() - INTERVAL '1 hour'),
    ('NORMAL', 300, 'MANUAL',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp DESC LIMIT 1),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), NOW() - INTERVAL '30 minutes'),
    ('OFF', NULL, 'MANUAL',
     (SELECT id FROM sensor_readings WHERE device_id = (SELECT id FROM devices WHERE device_id = 'POND-TEST-001') ORDER BY timestamp DESC LIMIT 1),
     (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'), NOW() - INTERVAL '10 minutes');

-- 6. Device status (for hardware/dashboard – shows device as online with latest reading)
INSERT INTO device_status (device_id, pump_running, pump_mode, led_status, quality_status, quality_score, is_online, last_heartbeat, network_ok, api_ok)
SELECT
    (SELECT id FROM devices WHERE device_id = 'POND-TEST-001'),
    false,
    'OFF',
    'GOOD',
    'CRITICAL',
    82,
    true,
    NOW(),
    true,
    true
ON CONFLICT (device_id) DO UPDATE SET
    quality_status = EXCLUDED.quality_status,
    quality_score = EXCLUDED.quality_score,
    last_heartbeat = EXCLUDED.last_heartbeat,
    updated_at = NOW();
