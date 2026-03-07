-- =============================================================================
-- schema_v3.sql  —  Hardware Control & Status Tables
-- Smart Fish Pond Monitoring System
-- =============================================================================
-- Apply AFTER schema_v1.sql and schema_v2.sql have been applied.
-- Adds bidirectional communication support between the Raspberry Pi hardware
-- agent and the web application:
--   • hardware_commands  : web dashboard → Pi command queue
--   • device_status      : Pi → web dashboard live heartbeat
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. hardware_commands
--    The web dashboard (admin/farmer) writes rows here to send commands to the
--    Raspberry Pi.  The Pi polls GET /api/devices/{id}/commands for 'pending'
--    rows, executes them, then acknowledges via PATCH …/commands/{cid}/ack.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hardware_commands (
    id               SERIAL PRIMARY KEY,
    device_id        INTEGER      NOT NULL REFERENCES devices(id) ON DELETE CASCADE,

    -- Command identifier.  Allowed values:
    --   PUMP_ON | PUMP_OFF | PUMP_SHORT | PUMP_LONG
    --   SYSTEM_SHUTDOWN | SYSTEM_RESTART | CLEAR_ALERT
    command          VARCHAR(50)  NOT NULL,

    -- Optional JSON payload (e.g. {"duration_seconds": 120})
    parameters       JSONB        NOT NULL DEFAULT '{}',

    -- Who issued the command from the web UI (NULL = system-generated)
    issued_by        INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    issued_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Lifecycle: pending → acknowledged → executed  (or failed)
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','acknowledged','executed','failed')),

    acknowledged_at  TIMESTAMPTZ,   -- Set when Pi confirms receipt
    executed_at      TIMESTAMPTZ,   -- Set when Pi finishes execution
    error_message    TEXT           -- Populated on failure
);

-- Index to let the Pi quickly poll its own pending commands
CREATE INDEX IF NOT EXISTS idx_hardware_commands_device_pending
    ON hardware_commands (device_id, status)
    WHERE status = 'pending';

-- Index for the dashboard to show recent command history per device
CREATE INDEX IF NOT EXISTS idx_hardware_commands_issued_at
    ON hardware_commands (device_id, issued_at DESC);

-- ---------------------------------------------------------------------------
-- 2. device_status
--    The Pi pushes its live hardware state every ~15 seconds.  One row per
--    device (UPSERT on device_id).  The dashboard reads this for the live
--    status panel (LED indicators, pump state, connectivity badge, etc.)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS device_status (
    id               SERIAL PRIMARY KEY,
    device_id        INTEGER      NOT NULL REFERENCES devices(id) ON DELETE CASCADE UNIQUE,

    -- GPIO / control state
    pump_running     BOOLEAN      NOT NULL DEFAULT FALSE,
    pump_mode        VARCHAR(20),                    -- OFF | SHORT | NORMAL | LONG
    led_status       VARCHAR(20),                    -- GOOD | WARNING | CRITICAL
    buzzer_active    BOOLEAN      NOT NULL DEFAULT FALSE,

    -- Latest water quality summary (mirrors last sensor reading)
    quality_status   VARCHAR(20),                    -- GOOD | WARNING | CRITICAL
    quality_score    SMALLINT,                       -- 0–150

    -- Connectivity & health
    is_online        BOOLEAN      NOT NULL DEFAULT FALSE,
    last_heartbeat   TIMESTAMPTZ,                   -- Last time Pi sent this row
    uptime_seconds   INTEGER,                        -- Seconds since Pi process started
    network_ok       BOOLEAN      NOT NULL DEFAULT TRUE,
    thingspeak_ok    BOOLEAN      NOT NULL DEFAULT TRUE,
    api_ok           BOOLEAN      NOT NULL DEFAULT TRUE,

    -- Thread / watchdog health (serialised as JSON for flexibility)
    thread_health    JSONB        NOT NULL DEFAULT '{}',

    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 3. Utility view — useful for the dashboard admin overview
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_device_overview AS
SELECT
    d.id                                   AS device_id,
    d.device_id                            AS device_uid,
    d.name                                 AS device_name,
    d.location_description,
    o.name                                 AS organization,
    ds.is_online,
    ds.last_heartbeat,
    ds.pump_running,
    ds.led_status,
    ds.quality_status,
    ds.quality_score,
    ds.network_ok,
    ds.uptime_seconds,
    -- Last sensor reading (latest row)
    sr.temperature,
    sr.ph,
    sr.ec,
    sr.nitrogen,
    sr.phosphorus,
    sr.turbidity,
    sr.timestamp                           AS last_reading_at,
    -- Pending command count
    (SELECT COUNT(*) FROM hardware_commands hc
     WHERE hc.device_id = d.id AND hc.status = 'pending')
                                           AS pending_command_count
FROM devices d
LEFT JOIN organizations o    ON d.organization_id = o.id
LEFT JOIN device_status  ds  ON ds.device_id      = d.id
LEFT JOIN LATERAL (
    SELECT temperature, ph, ec, nitrogen, phosphorus, turbidity, timestamp
    FROM   sensor_readings
    WHERE  device_id = d.id
    ORDER  BY timestamp DESC
    LIMIT  1
) sr ON true;
