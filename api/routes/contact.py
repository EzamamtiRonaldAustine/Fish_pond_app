# api/routes/contact.py
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
import logging
import datetime
from ..database import get_db_connection
from ..utils import require_role, get_user_from_token
from ..mail_utils import send_email

contact_bp = Blueprint('contact', __name__)
logger = logging.getLogger(__name__)

def determine_priority(subject, message):
    """Automatically assigns a priority level based on text content."""
    urgent_keywords = ['emergency', 'urgent', 'dying', 'death', 'failure', 'broken', 'critical', 'immediately']
    combined_text = (subject + ' ' + message).lower()
    
    for kw in urgent_keywords:
        if kw in combined_text:
            return 'High'
            
    if 'device' in subject.lower() or 'sensor' in subject.lower():
        return 'Medium'
        
    return 'Normal'

@contact_bp.route('/contact/submit', methods=['POST'])
def submit_message():
    """Public endpoint to submit a contact message."""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required_fields = ['name', 'email', 'subject', 'message']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing {field}'}), 400

    priority = determine_priority(data['subject'], data['message'])
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        cur = conn.cursor()
        
        insert_sql = """
            INSERT INTO contact_messages 
            (sender_name, sender_email, sender_phone, subject, message, priority)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(insert_sql, (
            data['name'], 
            data['email'], 
            data.get('phone', ''), 
            data['subject'], 
            data['message'],
            priority
        ))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'message': 'Message sent successfully. We will get back to you soon!'}), 201

    except Exception as e:
        logger.error(f"Error saving message: {e}")
        conn.rollback()
        return jsonify({'error': 'Failed to submit message'}), 500

@contact_bp.route('/contact/messages', methods=['GET'])
@require_role('admin')
def get_messages():
    """Admin endpoint to retrieve all messages with user verification status."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # We left join with users to see if the sender is verified
        query = """
            SELECT m.*, 
                   CASE WHEN u.id IS NOT NULL THEN TRUE ELSE FALSE END as is_verified_user,
                   u.role as sender_role
            FROM contact_messages m
            LEFT JOIN users u ON m.sender_email = u.email
            ORDER BY 
                CASE WHEN m.priority = 'High' AND m.is_replied = FALSE THEN 1
                     WHEN m.is_replied = FALSE THEN 2
                     ELSE 3 END,
                m.created_at DESC
        """
        cur.execute(query)
        messages = cur.fetchall()
        
        # Serialize datetimes
        msg_list = []
        for msg in messages:
            msg_dict = dict(msg)
            if msg_dict.get('created_at'):
                msg_dict['created_at'] = msg_dict['created_at'].isoformat()
            if msg_dict.get('replied_at'):
                msg_dict['replied_at'] = msg_dict['replied_at'].isoformat()
            msg_list.append(msg_dict)

        cur.close()
        conn.close()
        return jsonify({'messages': msg_list}), 200

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({'error': 'Failed to fetch messages'}), 500

@contact_bp.route('/contact/messages/<int:msg_id>/read', methods=['POST'])
@require_role('admin')
def mark_read(msg_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        cur = conn.cursor()
        cur.execute("UPDATE contact_messages SET is_read = TRUE WHERE id = %s", (msg_id,))
        if cur.rowcount == 0:
            return jsonify({'error': 'Message not found'}), 404
            
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Marked as read'}), 200
    except Exception as e:
        logger.error(f"Error marking read: {e}")
        return jsonify({'error': 'Failed to update'}), 500

@contact_bp.route('/contact/messages/<int:msg_id>/reply', methods=['POST'])
@require_role('admin')
def reply_message(msg_id):
    data = request.json
    reply_text = data.get('reply_text')
    
    if not reply_text:
        return jsonify({'error': 'Reply text is required'}), 400
        
    admin_user = get_user_from_token()

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM contact_messages WHERE id = %s", (msg_id,))
        msg = cur.fetchone()
        
        if not msg:
            cur.close()
            conn.close()
            return jsonify({'error': 'Message not found'}), 404
            
        if msg['is_replied']:
            cur.close()
            conn.close()
            return jsonify({'error': 'Message has already been replied to'}), 400

        # Formulate HTML Email
        subject = f"Re: {msg['subject']} - Fish Pond Support"
        body_text = f"Dear {msg['sender_name']},\n\n{reply_text}\n\n--\nAquaGuardian Supporting Team"
        
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2e7d32;">Fish Pond Support Response</h2>
                    <p>Dear {msg['sender_name']},</p>
                    <p style="white-space: pre-wrap;">{reply_text}</p>
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="font-size: 13px; color: #777;">
                        <strong>Your Original Message:</strong><br>
                        <em>"{msg['message']}"</em>
                    </p>
                </div>
            </body>
        </html>
        """

        # Attempt to send email
        email_sent = send_email(msg['sender_email'], subject, body_text, body_html)
        
        if not email_sent:
            cur.close()
            conn.close()
            return jsonify({'error': 'Failed to send email reply due to SMTP error.'}), 500

        # Update DB state
        cur.execute("""
            UPDATE contact_messages 
            SET is_replied = TRUE, 
                reply_text = %s, 
                replied_at = CURRENT_TIMESTAMP, 
                replied_by_id = %s,
                is_read = TRUE
            WHERE id = %s
        """, (reply_text, admin_user['id'], msg_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'message': 'Reply sent successfully'}), 200

    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        return jsonify({'error': 'Failed to process reply'}), 500
