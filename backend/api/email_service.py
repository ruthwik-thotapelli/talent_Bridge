import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def send_mail(to_email: str, subject: str, text: str, html: str):
    if not getattr(settings, "BREVO_API_KEY", None):
        print(f"[Email] Brevo API key not set. Skipping email send to {to_email}")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "Content-Type": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "Accept": "application/json",
    }
    payload = {
        "sender": {
            "name": getattr(settings, "SMTP_FROM_NAME", "TalentBridge"),
            "email": getattr(settings, "SMTP_FROM_EMAIL", "no-reply@talentbridge.com"),
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"[Email] Sent: {subject} => {to_email}")
    except Exception as e:
        print(f"[Email] Brevo email send failed: {e}")

def send_verification_email(to_email: str, name: str, verify_link: str):
    subject = "Verify your TalentBridge email"
    text = f"Hi {name or 'User'},\n\nWelcome to TalentBridge.\nPlease verify your email:\n{verify_link}"
    html = f"""
    <div style="font-family:sans-serif;padding:20px;">
      <h2>Verify Your Email</h2>
      <p>Hi {name or 'User'}, please click below to verify your email:</p>
      <a href="{verify_link}" style="padding:10px 20px;background:#16a34a;color:#fff;border-radius:6px;text-decoration:none;">Verify Email</a>
      <p>Or paste this link: {verify_link}</p>
    </div>
    """
    try:
        send_mail(to_email, subject, text, html)
    except Exception as e:
        print(f"[Email] Error in send_verification_email: {e}")

def send_reset_email(to_email: str, name: str, reset_link: str):
    subject = "Reset your TalentBridge password"
    text = f"Hi {name or 'User'},\n\nReset your password:\n{reset_link}"
    html = f"""
    <div style="font-family:sans-serif;padding:20px;">
      <h2>Reset Password</h2>
      <p>Click below to reset your password:</p>
      <a href="{reset_link}" style="padding:10px 20px;background:#4f46e5;color:#fff;border-radius:6px;text-decoration:none;">Reset Password</a>
    </div>
    """
    try:
        send_mail(to_email, subject, text, html)
    except Exception as e:
        print(f"[Email] Error in send_reset_email: {e}")

def send_welcome_email(to_email: str, name: str):
    subject = "Welcome to TalentBridge"
    text = f"Hi {name or 'User'},\n\nYour account has been verified!"
    html = f"<div style='font-family:sans-serif;padding:20px;'><h2>Welcome!</h2><p>Your email is verified.</p></div>"
    try:
        send_mail(to_email, subject, text, html)
    except Exception as e:
        print(f"[Email] Error in send_welcome_email: {e}")

def send_login_alert_email(to_email: str, name: str, meta: dict = None):
    meta = meta or {}
    subject = "New login to your TalentBridge account"
    text = f"Hi {name or 'User'},\n\nA login was detected.\nIP: {meta.get('ip')}\nTime: {meta.get('time')}"
    html = f"<div style='font-family:sans-serif;padding:20px;'><h2>New Login</h2><p>IP: {meta.get('ip')}</p><p>Time: {meta.get('time')}</p></div>"
    try:
        send_mail(to_email, subject, text, html)
    except Exception as e:
        print(f"[Email] Error in send_login_alert_email: {e}")
