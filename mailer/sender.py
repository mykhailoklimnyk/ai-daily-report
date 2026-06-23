import os
import re
import html
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Matches markdown links: [visible text](https://url)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
# Matches *italic* spans (used only for the disclaimer line)
_ITALIC_RE = re.compile(r"\*([^*\n]+)\*")


def report_to_plain(report: str) -> str:
    """Plain-text view: '[text](url)' -> 'text (url)', drop '*' emphasis markers."""
    text = _MD_LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", report)
    return _ITALIC_RE.sub(r"\1", text)


def report_to_html(report: str) -> str:
    """HTML view with clickable links, safe escaping and line breaks preserved."""
    escaped = html.escape(report, quote=False)
    # Brackets/parens survive escaping, so markdown links still match here.
    escaped = _MD_LINK_RE.sub(
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', escaped
    )
    escaped = _ITALIC_RE.sub(r"<em>\1</em>", escaped)

    parts = []
    for line in escaped.split("\n"):
        parts.append("<hr>" if line.strip() == "---" else line + "<br>")
    body = "\n".join(parts)

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; '
        'line-height: 1.55; color: #222;">'
        f"{body}"
        "</body></html>"
    )


class EmailSender:
    """Class for sending emails via SMTP."""

    def __init__(self):
        """Initialize the EmailSender with credentials from environment variables."""
        self.smtp_server = os.getenv("SMTP_SERVER", 'smtp.gmail.com')
        self.smtp_port = int(os.getenv("SMTP_PORT", 465))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.sender_email = os.getenv("SENDER_EMAIL", self.smtp_user)
        self.use_ssl = os.getenv("SMTP_USE_SSL", "true").lower() == "true"

        # Verify credentials are available
        if not all([self.smtp_server, self.smtp_port, self.smtp_user, self.smtp_password]):
            raise ValueError("Missing SMTP configuration in environment variables")

    def send_email(self, recipient_emails: List[str], subject: str, body: str,
                   html_body: Optional[str] = None) -> bool:
        """
        Send an email to one or more recipients.

        Args:
            recipient_emails: List of email addresses to send to
            subject: Email subject line
            body: Plain-text body content
            html_body: Optional HTML body; when provided the message is sent as
                multipart/alternative so clients can render clickable links.

        Returns:
            True if the email was sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(recipient_emails)
            msg["Subject"] = subject

            # Plain-text part first, HTML last (clients prefer the last viable part)
            msg.attach(MIMEText(body, "plain", "utf-8"))
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Connect to SMTP server and send
            if self.use_ssl:
                # Use SSL (port 465)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
                # Use STARTTLS (port 587)
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)

            logger.info(f"Email sent successfully to {', '.join(recipient_emails)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

    def send_report(self, recipient_emails: List[str], report: str, date: Optional[datetime] = None) -> bool:
        """
        Send a productivity report via email.

        Args:
            recipient_emails: List of email addresses to send the report to
            report: The generated report content (may contain markdown links)
            date: Date of the report (defaults to today)

        Returns:
            True if the email was sent successfully, False otherwise
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y-%m-%d")
        subject = f"Щоденний звіт - {date_str}"

        # Send both a plain-text and an HTML version (HTML keeps clickable Jira links)
        return self.send_email(
            recipient_emails,
            subject,
            body=report_to_plain(report),
            html_body=report_to_html(report),
        )
