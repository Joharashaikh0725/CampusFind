import os
import smtplib
import threading
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def send_email(to, subject, body):
    """Send a plain text email. If SMTP is not configured, print it to the console."""
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()

    if not (host and user and password):
        print(f"[email not configured] To: {to} | {subject}\n{body}\n")
        return False

    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", user)
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as error:
        print(f"[email failed] To: {to} | {error}")
        return False


def send_email_async(to, subject, body):
    threading.Thread(
        target=send_email,
        args=(to, subject, body),
        daemon=True
    ).start()
