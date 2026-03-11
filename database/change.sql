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
    (
        SELECT COUNT(DISTINCT d.id)
        FROM devices d
        LEFT JOIN device_permissions dp ON dp.device_id = d.id AND dp.user_id = u.id
        WHERE d.created_by = u.id OR dp.user_id IS NOT NULL
    ) AS device_count
FROM users u
LEFT JOIN organizations o ON u.organization_id = o.id
GROUP BY u.id, o.name
ORDER BY u.created_at DESC;