"""
api/routes/control.py — Hardware Command & Live-Status Endpoints
================================================================
Bidirectional communication layer between the web dashboard and the
Raspberry Pi hardware agent.

Endpoint summary
----------------
POST   /api/devices/{id}/commands       Queue a command (admin/farmer JWT)
GET    /api/devices/{id}/commands       Pi polls pending commands (device key)
PATCH  /api/devices/{id}/commands/{cid}/ack  Pi acknowledges a command (device key)
GET    /api/devices/{id}/status         Fetch live hardware state (any JWT)
POST   /api/devices/{id}/status         Pi pushes heartbeat (device key)

Authentication patterns
-----------------------
- Web users  → standard JWT bearer token (existing auth flow)
- Raspberry Pi → X-Device-Key header (pre-shared secret in .env)
"""

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from psycopg2.extras import RealDictCursor, Json as PgJson
from datetime import datetime
import logging
import os

from ..database import get_db_connection
from ..utils import get_user_from_token, check_device_access

control_bp = Blueprint("control", __name__)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Allowed hardware commands (whitelist for security)
# ─────────────────────────────────────────────────────────────────────────────
VALID_COMMANDS = frozenset({
    "PUMP_ON",
    "PUMP_OFF",
    "PUMP_SHORT",
    "PUMP_NORMAL",
    "PUMP_LONG",
    "SYSTEM_SHUTDOWN",
    "SYSTEM_RESTART",
    "CLEAR_ALERT",
})


# ─────────────────────────────────────────────────────────────────────────────
# Authentication helpers
# ─────────────────────────────────────────────────────────────────────────────

def _verify_device_key() -> bool:
    """
    Validate the X-Device-Key header against the DEVICE_API_KEY env var.
    Returns True if the key matches, False otherwise.
    """
    expected = os.environ.get("DEVICE_API_KEY", "")
    if not expected:
        logger.error("DEVICE_API_KEY is not configured in the API environment")
        return False
    provided = request.headers.get("X-Device-Key", "")
    return expected == provided


def _device_key_required(f):
    """Decorator: reject requests that don't carry a valid device key."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not _verify_device_key():
            return jsonify({"error": "Invalid or missing device key"}), 401
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# ① POST /api/devices/<id>/commands   —   Web → Pi command queue
# ─────────────────────────────────────────────────────────────────────────────

@control_bp.route("/devices/<int:device_id>/commands", methods=["POST"])
@jwt_required()
def queue_command(device_id: int):
    """
    Queue a hardware command for the specified device.

    Only admin and farmer roles may issue commands.
    The Pi will pick this up on its next poll cycle (every ~10 s).

    Request body (JSON)
    -------------------
    {
        "command":    "PUMP_ON",          # required — see VALID_COMMANDS
        "parameters": {"mode": "NORMAL"}  # optional — passed to Pi as-is
    }

    Response 201
    ------------
    { "command_id": 42, "message": "Command queued", "command": "PUMP_ON" }
    """
    user = get_user_from_token()
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["role"] not in ("admin", "farmer"):
        return jsonify({"error": "Only admin or farmer may issue commands"}), 403
    if user["role"] != "admin" and not check_device_access(user["id"], device_id):
        return jsonify({"error": "Access denied to this device"}), 403

    body = request.get_json(silent=True) or {}
    command = str(body.get("command", "")).upper().strip()
    parameters = body.get("parameters", {})

    if not command:
        return jsonify({"error": "'command' field is required"}), 400
    if command not in VALID_COMMANDS:
        return jsonify({
            "error": f"Invalid command '{command}'",
            "valid_commands": sorted(VALID_COMMANDS),
        }), 400
    if not isinstance(parameters, dict):
        return jsonify({"error": "'parameters' must be a JSON object"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Verify device exists
        cur.execute("SELECT id FROM devices WHERE id = %s", (device_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Device not found"}), 404

        # Insert command into queue
        # PgJson() wraps the dict so psycopg2 correctly serialises it for the JSONB column
        cur.execute(
            """
            INSERT INTO hardware_commands
                (device_id, command, parameters, issued_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (device_id, command, PgJson(parameters), user["id"]),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        command_id = row["id"]
        logger.info(
            f"Command queued: #{command_id} {command} for device {device_id} "
            f"by {user['username']}"
        )
        return jsonify({
            "command_id": command_id,
            "message":    "Command queued — Pi will execute on next poll",
            "command":    command,
        }), 201

    except Exception as exc:
        logger.error(f"Error queuing command: {exc}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"error": "Failed to queue command"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ② GET /api/devices/<id>/commands   —   Pi polls for pending commands
# ─────────────────────────────────────────────────────────────────────────────

@control_bp.route("/devices/<int:device_id>/commands", methods=["GET"])
@_device_key_required
def get_pending_commands(device_id: int):
    """
    Return a list of 'pending' commands the Pi should execute.
    Called every ~10 s by the Pi hardware agent.
    Also marks returned commands as 'acknowledged'.

    Response 200
    ------------
    {
        "commands": [
            { "id": 42, "command": "PUMP_ON", "parameters": {}, "issued_at": "..." }
        ]
    }
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch pending commands
        cur.execute(
            """
            SELECT id, command, parameters, issued_at
            FROM hardware_commands
            WHERE device_id = %s AND status = 'pending'
            ORDER BY issued_at ASC
            """,
            (device_id,),
        )
        rows = cur.fetchall()

        if rows:
            ids = [r["id"] for r in rows]
            # Mark them as acknowledged immediately so they aren't re-delivered
            cur.execute(
                """
                UPDATE hardware_commands
                SET status = 'acknowledged', acknowledged_at = NOW()
                WHERE id = ANY(%s)
                """,
                (ids,),
            )
            conn.commit()

        cur.close()
        conn.close()

        commands = [
            {
                "id":          row["id"],
                "command":     row["command"],
                "parameters":  row["parameters"] or {},
                "issued_at":   row["issued_at"].isoformat() if row["issued_at"] else None,
            }
            for row in rows
        ]
        return jsonify({"commands": commands}), 200

    except Exception as exc:
        logger.error(f"Error fetching commands: {exc}")
        return jsonify({"error": "Failed to fetch commands"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ③ PATCH /api/devices/<id>/commands/<cid>/ack  —  Pi marks command done
# ─────────────────────────────────────────────────────────────────────────────

@control_bp.route(
    "/devices/<int:device_id>/commands/<int:command_id>/ack", methods=["PATCH"]
)
@_device_key_required
def ack_command(device_id: int, command_id: int):
    """
    Pi calls this once a command has been executed (or failed).

    Request body (JSON)
    -------------------
    {
        "status":        "executed",          # "executed" or "failed"
        "error_message": "optional failure reason"
    }

    Response 200
    ------------
    { "message": "Command updated" }
    """
    body = request.get_json(silent=True) or {}
    status = body.get("status", "executed")
    error_msg = body.get("error_message")

    if status not in ("executed", "failed"):
        return jsonify({"error": "status must be 'executed' or 'failed'"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE hardware_commands
            SET status        = %s,
                executed_at   = NOW(),
                error_message = %s
            WHERE id = %s AND device_id = %s
            """,
            (status, error_msg, command_id, device_id),
        )
        affected = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()

        if affected == 0:
            return jsonify({"error": "Command not found"}), 404

        logger.info(f"Command #{command_id} → {status}")
        return jsonify({"message": "Command updated"}), 200

    except Exception as exc:
        logger.error(f"Error acknowledging command: {exc}")
        return jsonify({"error": "Failed to update command"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ④ GET /api/devices/<id>/status   —   Dashboard reads live hardware state
# ─────────────────────────────────────────────────────────────────────────────

@control_bp.route("/devices/<int:device_id>/status", methods=["GET"])
@jwt_required()
def get_device_status(device_id: int):
    """
    Return the live hardware status for the specified device.
    Data is sourced from the device_status table (Pi heartbeat).

    Response 200
    ------------
    {
        "device_id":      1,
        "is_online":      true,
        "pump_running":   false,
        "pump_mode":      "OFF",
        "led_status":     "GOOD",
        "quality_status": "GOOD",
        "quality_score":  12,
        "uptime_seconds": 3600,
        "network_ok":     true,
        "thingspeak_ok":  true,
        "api_ok":         true,
        "last_heartbeat": "2026-03-03T14:00:00+03:00",
        "pending_commands": 0
    }
    """
    user = get_user_from_token()
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if user["role"] != "admin" and not check_device_access(user["id"], device_id):
        return jsonify({"error": "Access denied"}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Live status from heartbeat table
        cur.execute(
            """
            SELECT pump_running, pump_mode, led_status, buzzer_active,
                   quality_status, quality_score, is_online,
                   last_heartbeat, uptime_seconds,
                   network_ok, thingspeak_ok, api_ok, updated_at
            FROM device_status
            WHERE device_id = %s
            """,
            (device_id,),
        )
        status_row = cur.fetchone()

        # Pending command count
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM hardware_commands "
            "WHERE device_id = %s AND status IN ('pending','acknowledged')",
            (device_id,),
        )
        pending_row = cur.fetchone()
        cur.close()
        conn.close()

        # Device is considered offline if no heartbeat in the last 60 s
        is_online = False
        if status_row and status_row["last_heartbeat"]:
            from datetime import timezone
            heartbeat = status_row["last_heartbeat"]
            if heartbeat.tzinfo is None:
                # Naïve datetime from DB — compare with naïve UTC now
                age = (datetime.utcnow() - heartbeat).total_seconds()
            else:
                age = (datetime.now(timezone.utc) - heartbeat).total_seconds()
            is_online = age < 60

        if not status_row:
            return jsonify({
                "device_id":       device_id,
                "is_online":       False,
                "pump_running":    False,
                "pump_mode":       "OFF",
                "led_status":      None,
                "quality_status":  None,
                "quality_score":   None,
                "uptime_seconds":  None,
                "network_ok":      None,
                "thingspeak_ok":   None,
                "api_ok":          None,
                "last_heartbeat":  None,
                "pending_commands": pending_row["cnt"] if pending_row else 0,
                "message": "No heartbeat received from device yet",
            }), 200

        return jsonify({
            "device_id":       device_id,
            "is_online":       is_online,
            "pump_running":    status_row["pump_running"],
            "pump_mode":       status_row["pump_mode"],
            "led_status":      status_row["led_status"],
            "buzzer_active":   status_row["buzzer_active"],
            "quality_status":  status_row["quality_status"],
            "quality_score":   status_row["quality_score"],
            "uptime_seconds":  status_row["uptime_seconds"],
            "network_ok":      status_row["network_ok"],
            "thingspeak_ok":   status_row["thingspeak_ok"],
            "api_ok":          status_row["api_ok"],
            "last_heartbeat":  (
                status_row["last_heartbeat"].isoformat()
                if status_row["last_heartbeat"] else None
            ),
            "pending_commands": pending_row["cnt"] if pending_row else 0,
        }), 200

    except Exception as exc:
        logger.error(f"Error fetching device status: {exc}")
        return jsonify({"error": "Failed to fetch device status"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ⑤ POST /api/devices/<id>/status   —   Pi pushes live heartbeat
# ─────────────────────────────────────────────────────────────────────────────

@control_bp.route("/devices/<int:device_id>/status", methods=["POST"])
@_device_key_required
def update_device_status(device_id: int):
    """
    Upsert the live hardware state for a device.
    Called by the Pi every ~15 s (HEARTBEAT_INTERVAL in config.py).

    Request body (JSON)
    -------------------
    {
        "pump_running":   false,
        "pump_mode":      "OFF",
        "led_status":     "GOOD",
        "quality_status": "GOOD",
        "quality_score":  12,
        "is_online":      true,
        "uptime_seconds": 3600,
        "network_ok":     true,
        "thingspeak_ok":  true,
        "api_ok":         true
    }

    Response 200
    ------------
    { "message": "Status updated" }
    """
    body = request.get_json(silent=True) or {}

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO device_status (
                device_id, pump_running, pump_mode, led_status, buzzer_active,
                quality_status, quality_score, is_online, last_heartbeat,
                uptime_seconds, network_ok, thingspeak_ok, api_ok, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, NOW())
            ON CONFLICT (device_id) DO UPDATE SET
                pump_running   = EXCLUDED.pump_running,
                pump_mode      = EXCLUDED.pump_mode,
                led_status     = EXCLUDED.led_status,
                buzzer_active  = EXCLUDED.buzzer_active,
                quality_status = EXCLUDED.quality_status,
                quality_score  = EXCLUDED.quality_score,
                is_online      = EXCLUDED.is_online,
                last_heartbeat = NOW(),
                uptime_seconds = EXCLUDED.uptime_seconds,
                network_ok     = EXCLUDED.network_ok,
                thingspeak_ok  = EXCLUDED.thingspeak_ok,
                api_ok         = EXCLUDED.api_ok,
                updated_at     = NOW()
            """,
            (
                device_id,
                body.get("pump_running", False),
                body.get("pump_mode",    "OFF"),
                body.get("led_status",   "GOOD"),
                body.get("buzzer_active", False),
                body.get("quality_status", "GOOD"),
                body.get("quality_score",  0),
                body.get("is_online",    True),
                body.get("uptime_seconds"),
                body.get("network_ok",    True),
                body.get("thingspeak_ok", True),
                body.get("api_ok",        True),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Status updated"}), 200

    except Exception as exc:
        logger.error(f"Error updating device status: {exc}")
        return jsonify({"error": "Failed to update status"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ⑥ GET /api/devices/<id>/commands/history   —   Web command audit log
# ─────────────────────────────────────────────────────────────────────────────

@control_bp.route("/devices/<int:device_id>/commands/history", methods=["GET"])
@jwt_required()
def get_command_history(device_id: int):
    """
    Return recent command history for a device (admin/farmer only).

    Query params
    ------------
    limit  — int, default 20, max 100
    """
    user = get_user_from_token()
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["role"] not in ("admin", "farmer"):
        return jsonify({"error": "Access denied"}), 403
    if user["role"] != "admin" and not check_device_access(user["id"], device_id):
        return jsonify({"error": "Access denied to this device"}), 403

    limit = min(int(request.args.get("limit", 20)), 100)

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT hc.id, hc.command, hc.parameters, hc.status,
                   hc.issued_at, hc.acknowledged_at, hc.executed_at,
                   hc.error_message,
                   u.username AS issued_by_username
            FROM hardware_commands hc
            LEFT JOIN users u ON hc.issued_by = u.id
            WHERE hc.device_id = %s
            ORDER BY hc.issued_at DESC
            LIMIT %s
            """,
            (device_id, limit),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        history = []
        for row in rows:
            entry = dict(row)
            for ts_field in ("issued_at", "acknowledged_at", "executed_at"):
                if entry.get(ts_field):
                    entry[ts_field] = entry[ts_field].isoformat()
            history.append(entry)

        return jsonify({"history": history, "device_id": device_id}), 200

    except Exception as exc:
        logger.error(f"Error fetching command history: {exc}")
        return jsonify({"error": "Failed to fetch command history"}), 500
