"""
Transactional email for verification and password-reset codes.

Two providers are supported:
- Brevo's HTTPS API (BREVO_API_KEY): works on hosts that block outbound SMTP, such as Render's
  free tier. A single verified sender address is enough; no domain is required.
- SMTP (SMTP_HOST, e.g. Gmail with an app password): convenient for local development.

Secrets are never logged. If no provider is configured, email features are switched off and
sign-up works without verification.
"""
import asyncio
import html
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

import httpx

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class EmailDeliveryError(Exception):
    """The email provider rejected the message or could not be reached."""


class EmailService:
    @property
    def enabled(self) -> bool:
        return settings.email_enabled

    async def send(self, to_email: str, subject: str, text: str, html_body: str) -> None:
        provider = settings.email_provider
        if provider == "brevo":
            await self._send_brevo(to_email, subject, text, html_body)
        elif provider == "smtp":
            await asyncio.to_thread(self._send_smtp, to_email, subject, text, html_body)
        else:
            raise EmailDeliveryError("No email provider is configured.")

    async def _send_brevo(self, to_email: str, subject: str, text: str, html_body: str) -> None:
        payload = {
            "sender": {"email": settings.email_from_address, "name": settings.email_from_name},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text,
        }
        headers = {"api-key": settings.brevo_api_key or "", "accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(BREVO_SEND_URL, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise EmailDeliveryError(f"Email provider unreachable: {type(e).__name__}") from None
        if res.status_code >= 300:
            raise EmailDeliveryError(f"Email provider returned HTTP {res.status_code}")

    def _send_smtp(self, to_email: str, subject: str, text: str, html_body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{settings.email_from_name} <{settings.email_from_address}>"
        msg["To"] = to_email
        msg.set_content(text)
        msg.add_alternative(html_body, subtype="html")
        context = ssl.create_default_context()
        try:
            if settings.smtp_port == 465:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=15) as server:
                    self._login(server)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                    server.ehlo()
                    if server.has_extn("starttls"):
                        server.starttls(context=context)
                        server.ehlo()
                    elif settings.smtp_host not in ("localhost", "127.0.0.1") or settings.smtp_password:
                        # Never send credentials or codes in plain text to a remote server
                        raise EmailDeliveryError("SMTP server does not support STARTTLS")
                    self._login(server)
                    server.send_message(msg)
        except (smtplib.SMTPException, OSError) as e:
            raise EmailDeliveryError(f"SMTP delivery failed: {type(e).__name__}") from None

    @staticmethod
    def _login(server: smtplib.SMTP) -> None:
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)

    async def send_code(self, to_email: str, name: Optional[str], code: str, purpose: str) -> None:
        minutes = settings.email_code_ttl_minutes
        greeting = f"Hi {name.split()[0]}," if name and name.strip() else "Hi,"
        if purpose == "verify_email":
            subject = f"{code} is your LumoraAI verification code"
            intro = "Use this code to verify your email address and finish creating your LumoraAI account."
        else:
            subject = f"{code} is your LumoraAI password reset code"
            intro = "Use this code to reset your LumoraAI password."
        outro = (
            f"The code expires in {minutes} minutes. If you didn't request it, you can ignore this email; "
            "your account stays safe."
        )
        text = f"{greeting}\n\n{intro}\n\n    {code}\n\n{outro}\n\n— LumoraAI"
        html_body = _render_code_email(greeting, intro, code, outro)
        await self.send(to_email, subject, text, html_body)


def _render_code_email(greeting: str, intro: str, code: str, outro: str) -> str:
    g, i, c, o = (html.escape(s) for s in (greeting, intro, code, outro))
    return f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#1d2433">
  <table role="presentation" width="100%" style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:16px;padding:32px">
    <tr><td>
      <p style="margin:0 0 4px;font-size:18px;font-weight:bold;color:#2f6fed">LumoraAI</p>
      <p style="margin:24px 0 8px;font-size:15px">{g}</p>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.5">{i}</p>
      <p style="margin:0 0 20px;font-size:32px;letter-spacing:8px;font-weight:bold;text-align:center;background:#eef3fc;border-radius:12px;padding:16px">{c}</p>
      <p style="margin:0;font-size:13px;line-height:1.5;color:#5b6475">{o}</p>
    </td></tr>
  </table>
</body></html>"""


email_service = EmailService()
