-- ============================================================================
-- Railway Database Logic Adjustment
-- ============================================================================
-- Run these queries against your existing Railway PostgreSQL instance to fix 
-- the device scoping issue where new farmers see all devices in the organization.
-- ============================================================================

BEGIN;

-- 1. Update the User-Device Access View
-- Restricts visibility so farmers only see:
--  a) Devices they created (owner)
--  b) Devices they have explicit entries for in device_permissions
--  c) Admins still see everything
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
            WHEN d.created_by = u.id THEN 'owner'
            ELSE NULL
        END
    ) AS permission_level
FROM users u
LEFT JOIN devices d ON (
    u.role = 'admin' OR 
    d.created_by = u.id OR
    EXISTS (SELECT 1 FROM device_permissions dp2 WHERE dp2.user_id = u.id AND dp2.device_id = d.id)
)
LEFT JOIN device_permissions dp ON dp.user_id = u.id AND dp.device_id = d.id
WHERE u.is_active = TRUE;

-- 2. Update the user_has_devices Function
-- Returns TRUE only if the user owns a device or has explicit permission.
CREATE OR REPLACE FUNCTION user_has_devices(p_user_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    device_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO device_count
    FROM devices d
    LEFT JOIN device_permissions dp 
           ON dp.device_id = d.id 
          AND dp.user_id = p_user_id
    WHERE d.created_by = p_user_id
       OR dp.user_id IS NOT NULL;
    
    RETURN device_count > 0;
END;
$$ LANGUAGE plpgsql;

-- 3. Standardize Email Validation (Optional but Recommended)
ALTER TABLE users 
    DROP CONSTRAINT IF EXISTS users_email_check;

ALTER TABLE users 
    ADD CONSTRAINT users_email_check 
    CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

COMMIT;

-- VERIFICATION
-- Check access for a specific user ID:
-- SELECT * FROM v_user_device_access WHERE user_id = YOUR_USER_ID;
