# api/mail_utils.py
import smtplib
import os
import logging
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def generate_otp(length=6):
    """Generate a random 6-digit numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))

def send_email(to_email, subject, body_text, body_html=None):
    """
    Send an email using SMTP settings from environment variables.
    """
    smtp_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("MAIL_PORT", 587))
    smtp_user = os.environ.get("MAIL_USERNAME")
    smtp_password = os.environ.get("MAIL_PASSWORD") # App Password

    if not smtp_user or not smtp_password:
        logger.error("MAIL_USERNAME or MAIL_PASSWORD not configured. Cannot send email.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Fish Pond System <{smtp_user}>"
        msg["To"] = to_email

        # Attach plain text part
        msg.attach(MIMEText(body_text, "plain"))
        
        # Attach HTML part if provided
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        # Connect and send
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            
        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

def send_otp_email(to_email, otp_code):
    """Helper to send the 6-digit verification code to a user."""
    subject = "Your Verification Code - Fish Pond Management"
    
    body_text = f"Your verification code is: {otp_code}\n\nThis code will expire in 10 minutes. Please do not share this code with anyone."
    
    body_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #2e7d32; text-align: center;">Fish Pond Management System</h2>
                <p>Hello,</p>
                <p>You requested a verification code for your account. Please use the 6-digit code below to verify your identity:</p>
                <div style="background-color: #f4f4f4; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #333;">{otp_code}</span>
                </div>
                <p style="color: #d32f2f;"><strong>Important:</strong> This code will expire in 10 minutes. Please do not share this code with anyone.</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #777; text-align: center;">This is an automated system message. Please do not reply.</p>
            </div>
        </body>
    </html>
    """
    return send_email(to_email, subject, body_text, body_html)
