-- ============================================================================
-- Railway Database Initialization Script
-- ============================================================================
-- Run this ONCE against the Railway PostgreSQL instance to create all tables,
-- views and functions required by the API + dashboard.
--
-- This script is self‑contained and intentionally:
--   • Creates ONLY the required schema
--   • Adds a single default admin user (admin / admin123 – CHANGE LATER)
--   • Does NOT include any private/local users, test data or custom DB users
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CORE MONITORING SCHEMA (from pond_sql.sql, trimmed)
--    sensor_readings, users, alerts, pond_config, pump_log
-- ============================================================================

CREATE TABLE IF NOT EXISTS sensor_readings (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    temperature     DECIMAL(5, 2),
    ph              DECIMAL(4, 2),
    ec              DECIMAL(8, 2),
    nitrogen        DECIMAL(8, 2),
    phosphorus      DECIMAL(8, 2),
    turbidity       BOOLEAN,
    quality_status  VARCHAR(20) CHECK (quality_status IN ('GOOD', 'WARNING', 'CRITICAL')),
    quality_score   INTEGER CHECK (quality_score >= 0 AND quality_score <= 100),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp 
    ON sensor_readings(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_status 
    ON sensor_readings(quality_status);

CREATE TABLE IF NOT EXISTS users (
    id             SERIAL PRIMARY KEY,
    username       VARCHAR(50) UNIQUE NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    email          VARCHAR(100),
    full_name      VARCHAR(100),
    role           VARCHAR(20) DEFAULT 'farmer' CHECK (role IN ('farmer', 'admin', 'viewer')),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login     TIMESTAMP,
    is_active      BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_users_username 
    ON users(username);

CREATE TABLE IF NOT EXISTS alerts (
    id                 SERIAL PRIMARY KEY,
    timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    alert_type         VARCHAR(50) NOT NULL,
    severity           VARCHAR(20) CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    message            TEXT NOT NULL,
    sensor_reading_id  INTEGER REFERENCES sensor_readings(id) ON DELETE SET NULL,
    acknowledged       BOOLEAN DEFAULT FALSE,
    acknowledged_at    TIMESTAMP,
    acknowledged_by    INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged 
    ON alerts(acknowledged, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_type 
    ON alerts(alert_type);

CREATE TABLE IF NOT EXISTS pond_config (
    id             SERIAL PRIMARY KEY,
    config_key     VARCHAR(100) UNIQUE NOT NULL,
    config_value   TEXT,
    description    TEXT,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by     INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pump_log (
    id                 SERIAL PRIMARY KEY,
    timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    mode               VARCHAR(20) CHECK (mode IN ('SHORT', 'NORMAL', 'LONG', 'MANUAL', 'OFF')),
    duration_seconds   INTEGER,
    triggered_by       VARCHAR(50),
    sensor_reading_id  INTEGER REFERENCES sensor_readings(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pump_log_timestamp 
    ON pump_log(timestamp DESC);

CREATE OR REPLACE VIEW latest_readings AS
SELECT 
    sr.*,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - sr.timestamp)) / 60 AS minutes_ago
FROM sensor_readings sr
ORDER BY sr.timestamp DESC
LIMIT 1;

CREATE OR REPLACE VIEW daily_statistics AS
SELECT 
    DATE(timestamp)                              AS date,
    COUNT(*)                                     AS reading_count,
    AVG(temperature)                             AS avg_temperature,
    AVG(ph)                                      AS avg_ph,
    AVG(ec)                                      AS avg_ec,
    AVG(nitrogen)                                AS avg_nitrogen,
    AVG(phosphorus)                              AS avg_phosphorus,
    COUNT(CASE WHEN quality_status = 'CRITICAL' THEN 1 END) AS critical_count,
    COUNT(CASE WHEN quality_status = 'WARNING'  THEN 1 END) AS warning_count
FROM sensor_readings
WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(timestamp)
ORDER BY date DESC;

CREATE OR REPLACE FUNCTION clean_old_readings(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM sensor_readings
    WHERE timestamp < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE sensor_readings IS 'Stores all sensor readings from the fish pond monitoring system';
COMMENT ON TABLE users IS 'User accounts for web dashboard authentication';
COMMENT ON TABLE alerts IS 'System alerts and notifications';
COMMENT ON TABLE pond_config IS 'System configuration parameters';
COMMENT ON TABLE pump_log IS 'Log of pump activation events';

COMMENT ON COLUMN sensor_readings.quality_status IS 'Overall water quality status: GOOD, WARNING, or CRITICAL';
COMMENT ON COLUMN sensor_readings.quality_score IS 'Water quality score from 0-100 (lower is better)';
COMMENT ON COLUMN users.role IS 'User role: farmer (default), admin, or viewer';

-- ============================================================================
-- 2. MULTI‑TENANT / ORGANIZATION SCHEMA (from migrate_to_v2.sql, trimmed)
--    organizations, devices, permissions, sessions, notification preferences
-- ============================================================================

CREATE TABLE IF NOT EXISTS organizations (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    contact_email    VARCHAR(100),
    contact_phone    VARCHAR(20),
    address          TEXT,
    subscription_tier VARCHAR(20) DEFAULT 'basic',
    max_devices      INTEGER DEFAULT 5,
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS devices (
    id                 SERIAL PRIMARY KEY,
    device_id          VARCHAR(50) UNIQUE NOT NULL,
    name               VARCHAR(100) NOT NULL,
    description        TEXT,
    organization_id    INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    raspberry_pi_ip    VARCHAR(45),
    raspberry_pi_mac   VARCHAR(17),
    hardware_version   VARCHAR(20),
    firmware_version   VARCHAR(20),
    location_gps       VARCHAR(100),
    location_description TEXT,
    status             VARCHAR(20) DEFAULT 'active',
    health_status      VARCHAR(20) DEFAULT 'healthy',
    last_seen          TIMESTAMP,
    last_reading_at    TIMESTAMP,
    reading_interval   INTEGER DEFAULT 300,
    alert_enabled      BOOLEAN DEFAULT TRUE,
    auto_pump_enabled  BOOLEAN DEFAULT TRUE,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by         INTEGER REFERENCES users(id),
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes              TEXT
);

CREATE TABLE IF NOT EXISTS device_permissions (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id         INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    permission_level  VARCHAR(20) DEFAULT 'viewer',
    granted_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by        INTEGER REFERENCES users(id),
    expires_at        TIMESTAMP,
    UNIQUE(user_id, device_id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   VARCHAR(255) NOT NULL,
    ip_address   VARCHAR(45),
    user_agent   TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at   TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active    BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    id                 SERIAL PRIMARY KEY,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id          INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    email_enabled      BOOLEAN DEFAULT TRUE,
    sms_enabled        BOOLEAN DEFAULT TRUE,
    push_enabled       BOOLEAN DEFAULT FALSE,
    notify_critical    BOOLEAN DEFAULT TRUE,
    notify_warning     BOOLEAN DEFAULT TRUE,
    notify_info        BOOLEAN DEFAULT FALSE,
    quiet_hours_start  TIME,
    quiet_hours_end    TIME,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, device_id)
);

ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL;
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en';
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE sensor_readings 
    ADD COLUMN IF NOT EXISTS device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE;

ALTER TABLE alerts 
    ADD COLUMN IF NOT EXISTS device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE;

ALTER TABLE pump_log 
    ADD COLUMN IF NOT EXISTS device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_users_organization 
    ON users(organization_id, is_active);
CREATE INDEX IF NOT EXISTS idx_devices_organization 
    ON devices(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_devices_device_id 
    ON devices(device_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_device 
    ON sensor_readings(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_device 
    ON alerts(device_id, acknowledged, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_pump_log_device 
    ON pump_log(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_device_permissions_user 
    ON device_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_device_permissions_device 
    ON device_permissions(device_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token 
    ON user_sessions(token_hash, is_active);

CREATE OR REPLACE VIEW v_active_devices AS
SELECT 
    d.id,
    d.device_id,
    d.name,
    d.organization_id,
    o.name AS organization_name,
    d.status,
    d.health_status,
    d.last_seen,
    d.last_reading_at,
    sr.temperature,
    sr.ph,
    sr.quality_status,
    EXTRACT(EPOCH FROM (NOW() - d.last_seen)) / 60 AS minutes_since_last_seen
FROM devices d
LEFT JOIN organizations o ON d.organization_id = o.id
LEFT JOIN LATERAL (
    SELECT temperature, ph, quality_status, timestamp
    FROM sensor_readings
    WHERE device_id = d.id
    ORDER BY timestamp DESC
    LIMIT 1
) sr ON true
WHERE d.status = 'active' AND o.is_active = TRUE;

CREATE OR REPLACE VIEW v_user_device_access AS
SELECT 
    u.id            AS user_id,
    u.username,
    u.role,
    u.organization_id,
    d.id            AS device_id,
    d.device_id     AS device_identifier,
    d.name          AS device_name,
    COALESCE(
        dp.permission_level, 
        CASE 
            WHEN u.role = 'admin' THEN 'owner'
            WHEN u.organization_id = d.organization_id THEN 'owner'
            ELSE NULL
        END
    ) AS permission_level
FROM users u
LEFT JOIN devices d ON (
    u.role = 'admin' OR 
    u.organization_id = d.organization_id
)
LEFT JOIN device_permissions dp ON dp.user_id = u.id AND dp.device_id = d.id
WHERE u.is_active = TRUE;

CREATE OR REPLACE VIEW v_organization_stats AS
SELECT 
    o.id,
    o.name,
    COUNT(DISTINCT d.id) AS total_devices,
    COUNT(DISTINCT d.id) FILTER (WHERE d.status = 'active') AS active_devices,
    COUNT(DISTINCT u.id) AS total_users,
    COUNT(DISTINCT sr.id) FILTER (WHERE sr.timestamp >= NOW() - INTERVAL '24 hours') AS readings_24h,
    COUNT(DISTINCT a.id)  FILTER (WHERE a.timestamp >= NOW() - INTERVAL '24 hours' AND a.acknowledged = FALSE) AS unacknowledged_alerts_24h
FROM organizations o
LEFT JOIN devices d       ON d.organization_id = o.id
LEFT JOIN users u         ON u.organization_id = o.id AND u.is_active = TRUE
LEFT JOIN sensor_readings sr ON sr.device_id = d.id
LEFT JOIN alerts a        ON a.device_id = d.id
WHERE o.is_active = TRUE
GROUP BY o.id, o.name;

CREATE OR REPLACE FUNCTION user_has_device_access(
    p_user_id       INTEGER,
    p_device_id     INTEGER,
    p_required_level VARCHAR DEFAULT 'viewer'
) RETURNS BOOLEAN AS $$
DECLARE
    v_has_access BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM v_user_device_access
        WHERE user_id = p_user_id 
          AND device_id = p_device_id
          AND (
              permission_level = 'owner' OR
              (p_required_level = 'editor' AND permission_level IN ('owner', 'editor')) OR
              (p_required_level = 'viewer' AND permission_level IN ('owner', 'editor', 'viewer'))
          )
    ) INTO v_has_access;
    
    RETURN v_has_access;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_device_last_seen(p_device_id INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE devices 
    SET 
        last_seen = NOW(),
        last_reading_at = NOW(),
        status = CASE 
            WHEN status = 'inactive' THEN 'active'
            ELSE status
        END
    WHERE id = p_device_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. HARDWARE CONTROL & STATUS SCHEMA (from Raspberry.sql)
--    hardware_commands, device_status, v_device_overview
-- ============================================================================

CREATE TABLE IF NOT EXISTS hardware_commands (
    id               SERIAL PRIMARY KEY,
    device_id        INTEGER      NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    command          VARCHAR(50)  NOT NULL,
    parameters       JSONB        NOT NULL DEFAULT '{}',
    issued_by        INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    issued_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','acknowledged','executed','failed')),
    acknowledged_at  TIMESTAMPTZ,
    executed_at      TIMESTAMPTZ,
    error_message    TEXT
);

CREATE INDEX IF NOT EXISTS idx_hardware_commands_device_pending
    ON hardware_commands (device_id, status)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_hardware_commands_issued_at
    ON hardware_commands (device_id, issued_at DESC);

CREATE TABLE IF NOT EXISTS device_status (
    id               SERIAL PRIMARY KEY,
    device_id        INTEGER      NOT NULL REFERENCES devices(id) ON DELETE CASCADE UNIQUE,
    pump_running     BOOLEAN      NOT NULL DEFAULT FALSE,
    pump_mode        VARCHAR(20),
    led_status       VARCHAR(20),
    buzzer_active    BOOLEAN      NOT NULL DEFAULT FALSE,
    quality_status   VARCHAR(20),
    quality_score    SMALLINT,
    is_online        BOOLEAN      NOT NULL DEFAULT FALSE,
    last_heartbeat   TIMESTAMPTZ,
    uptime_seconds   INTEGER,
    network_ok       BOOLEAN      NOT NULL DEFAULT TRUE,
    thingspeak_ok    BOOLEAN      NOT NULL DEFAULT TRUE,
    api_ok           BOOLEAN      NOT NULL DEFAULT TRUE,
    thread_health    JSONB        NOT NULL DEFAULT '{}',
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_device_overview AS
SELECT
    d.id                    AS device_id,
    d.device_id             AS device_uid,
    d.name                  AS device_name,
    d.location_description,
    o.name                  AS organization,
    ds.is_online,
    ds.last_heartbeat,
    ds.pump_running,
    ds.led_status,
    ds.quality_status,
    ds.quality_score,
    ds.network_ok,
    ds.uptime_seconds,
    sr.temperature,
    sr.ph,
    sr.ec,
    sr.nitrogen,
    sr.phosphorus,
    sr.turbidity,
    sr.timestamp            AS last_reading_at,
    (SELECT COUNT(*) 
       FROM hardware_commands hc
      WHERE hc.device_id = d.id AND hc.status = 'pending') AS pending_command_count
FROM devices d
LEFT JOIN organizations o   ON d.organization_id = o.id
LEFT JOIN device_status ds  ON ds.device_id      = d.id
LEFT JOIN LATERAL (
    SELECT temperature, ph, ec, nitrogen, phosphorus, turbidity, timestamp
    FROM   sensor_readings
    WHERE  device_id = d.id
    ORDER  BY timestamp DESC
    LIMIT  1
) sr ON true;

-- ============================================================================
-- 4. ROLE / EMAIL CONSTRAINTS + SUMMARY VIEW + user_has_devices()
--    (from roles_views.sql, trimmed)
-- ============================================================================

ALTER TABLE users 
    DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE users 
    ADD CONSTRAINT users_role_check 
    CHECK (role IN ('admin', 'farmer'));

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_email_check;

ALTER TABLE users
    ADD CONSTRAINT users_email_check
    CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

ALTER TABLE users 
    ALTER COLUMN email SET NOT NULL;

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_email_unique;

ALTER TABLE users
    ADD CONSTRAINT users_email_unique UNIQUE (email);

CREATE OR REPLACE VIEW user_device_summary AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.full_name,
    u.role,
    u.organization_id,
    o.name AS organization_name,
    u.is_active,
    u.created_at,
    u.last_login,
    COUNT(d.id) AS device_count
FROM users u
LEFT JOIN organizations o ON u.organization_id = o.id
LEFT JOIN devices d       ON d.created_by      = u.id
GROUP BY u.id, o.name
ORDER BY u.created_at DESC;

CREATE OR REPLACE FUNCTION user_has_devices(p_user_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    device_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO device_count
    FROM devices
    WHERE created_by = p_user_id
       OR organization_id = (SELECT organization_id FROM users WHERE id = p_user_id);
    
    RETURN device_count > 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. MINIMAL SEED DATA (safe defaults for first login)
--    Admin user: username 'admin', password 'admin123' (plain – change ASAP)
-- ============================================================================

INSERT INTO organizations (id, name, subscription_tier, max_devices, is_active)
VALUES (1, 'Default Organization', 'basic', 5, TRUE)
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (
    username,
    password_hash,
    email,
    full_name,
    role,
    organization_id,
    is_active
)
VALUES (
    'admin',
    'admin123',                          -- legacy plain text, auto‑upgraded on first login
    'admin@example.com',
    'Default Admin',
    'admin',
    1,
    TRUE
)
ON CONFLICT (username) DO NOTHING;

COMMIT;
