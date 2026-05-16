"""
Centralized transactional email for authentication flows.

Templates are professional HTML; sending runs on a background thread so API
responses are not blocked by SMTP latency. Configure credentials via environment
variables (see mpanzi/settings.py).
"""

from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import escape, strip_tags

logger = logging.getLogger(__name__)


def _send_async(subject: str, html_body: str, text_body: str, to_email: str) -> None:
    def _run() -> None:
        try:
            send_mail(
                subject=subject,
                message=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_body,
                fail_silently=False,
            )
            logger.info("Email queued/sent successfully to %s subject=%s", to_email, subject)
        except Exception:
            logger.exception("Failed to send email to %s subject=%s", to_email, subject)

    threading.Thread(target=_run, daemon=True).start()


def _wrap_html(title: str, inner_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;background:#eef1f5;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0"
          style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;
          box-shadow:0 4px 24px rgba(15,23,42,.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#1e3a5f,#0f172a);color:#f8fafc;
              padding:28px 24px;font-size:22px;font-weight:700;">
              Mpanzi Ministries
            </td>
          </tr>
          <tr>
            <td style="padding:32px 28px;color:#334155;font-size:16px;line-height:1.65;">
              {inner_html}
            </td>
          </tr>
          <tr>
            <td style="padding:20px 28px;font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0;">
              If you did not request this message, you can safely ignore it.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_verification_email(email: str, code: str) -> None:
    inner = f"""
      <p style="margin-top:0;">Thank you for registering. Please verify your email address
      to activate your account.</p>
      <p>Your verification code is:</p>
      <p style="font-size:32px;letter-spacing:10px;font-weight:800;color:#0f172a;
        text-align:center;margin:28px 0;font-variant-numeric:tabular-nums;">
        {code}
      </p>
      <p style="margin-bottom:0;">This code expires in <strong>5 minutes</strong>.
      For your security, never share this code with anyone.</p>
    """
    html = _wrap_html("Verify your email", inner)
    text = strip_tags(inner)
    _send_async("Verify your Mpanzi account", html, text, email)


def send_password_reset_email(email: str, code: str) -> None:
    inner = f"""
      <p style="margin-top:0;">We received a request to reset the password for your account.</p>
      <p>Your password reset code is:</p>
      <p style="font-size:32px;letter-spacing:10px;font-weight:800;color:#b91c1c;
        text-align:center;margin:28px 0;font-variant-numeric:tabular-nums;">
        {code}
      </p>
      <p style="margin-bottom:0;">This code expires in <strong>5 minutes</strong>.
      If you did not request a reset, you can ignore this email.</p>
    """
    html = _wrap_html("Password reset", inner)
    text = strip_tags(inner)
    _send_async("Reset your Mpanzi password", html, text, email)


def send_welcome_email(email: str) -> None:
    inner = """
      <p style="margin-top:0;">Your email has been verified and your account is now active.</p>
      <p>We are glad you are part of the Mpanzi Ministries community.</p>
    """
    html = _wrap_html("Welcome", inner)
    text = strip_tags(inner)
    _send_async("Welcome to Mpanzi", html, text, email)


def send_password_changed_email(email: str) -> None:
    inner = """
      <p style="margin-top:0;">Your password was changed successfully.</p>
      <p>If you did not make this change, please reset your password immediately and contact support.</p>
    """
    html = _wrap_html("Password changed", inner)
    text = strip_tags(inner)
    _send_async("Your Mpanzi password was changed", html, text, email)


def _wrap_marketplace_order_html(title: str, inner_html: str) -> str:
    """Same layout as auth mail, with an order-specific footer."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
</head>
<body style="margin:0;background:#eef1f5;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0"
          style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;
          box-shadow:0 4px 24px rgba(15,23,42,.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#1e3a5f,#0f172a);color:#f8fafc;
              padding:28px 24px;font-size:22px;font-weight:700;">
              Mpanzi Ministries
            </td>
          </tr>
          <tr>
            <td style="padding:32px 28px;color:#334155;font-size:16px;line-height:1.65;">
              {inner_html}
            </td>
          </tr>
          <tr>
            <td style="padding:20px 28px;font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0;">
              This message was sent because your marketplace order on Mpanzi was updated.
              If you have questions, use the app or reply to this email.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_partner_giving_paid_confirmation(*, partnership, payment) -> None:
    """
    After AzamPay webhook marks a partnership gift as paid, email the donor.
    `partnership` must have `partner_type` and optionally `user` loaded.
    """
    from .models import Partnership  # noqa: PLC0415 — avoid circular import at module load

    assert isinstance(partnership, Partnership)

    to_email = ""
    recipient_name = "Friend"
    user = partnership.user
    if user and getattr(user, "email", None):
        to_email = str(user.email).strip()
        full = (user.get_full_name() or "").strip()
        if full:
            recipient_name = full
        elif getattr(user, "username", None):
            recipient_name = str(user.username).strip()
    if not to_email and partnership.guest_email:
        to_email = str(partnership.guest_email).strip()
        local = to_email.split("@", 1)[0] if to_email else ""
        if local:
            recipient_name = local.replace(".", " ").replace("_", " ").title()

    if not to_email:
        logger.warning(
            "Partner giving paid but no recipient email partnership_id=%s payment_id=%s",
            partnership.id,
            getattr(payment, "id", None),
        )
        return

    ptype = escape(str(partnership.partner_type.name))
    amt = escape(str(partnership.amount))
    cur = escape(str(partnership.currency))
    pay_id = escape(str(getattr(payment, "id", "")))
    prov_txn = escape(str(getattr(payment, "provider_transaction_id", "") or ""))
    util = escape(str(getattr(payment, "utility_reference", "") or ""))
    paid_at = partnership.paid_at
    if paid_at:
        local_dt = timezone.localtime(paid_at)
        when = escape(local_dt.strftime("%Y-%m-%d %H:%M %Z"))
    else:
        when = ""

    inner = f"""
      <p style="margin-top:0;">Dear {escape(recipient_name)},</p>
      <p>Thank you for your partnership with <strong>Mpanzi Ministries</strong>.
      Your gift has been received successfully.</p>
      <table role="presentation" cellpadding="0" cellspacing="0"
        style="width:100%;margin:20px 0;border-collapse:separate;border-spacing:0;
        border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Partner type</td>
            <td style="padding:12px 16px;">{ptype}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Amount</td>
            <td style="padding:12px 16px;">{amt} {cur}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Payment reference</td>
            <td style="padding:12px 16px;font-variant-numeric:tabular-nums;">{pay_id}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Provider transaction</td>
            <td style="padding:12px 16px;word-break:break-all;">{prov_txn or "—"}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Operator reference</td>
            <td style="padding:12px 16px;word-break:break-all;">{util or "—"}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Date</td>
            <td style="padding:12px 16px;">{when or "—"}</td></tr>
      </table>
      <p><strong>Next steps:</strong> keep this email as your receipt. Our team may follow up about recurring
      arrangements if you chose recurring giving.</p>
      <p style="margin-bottom:0;">Questions? Reply to this email or contact us through the Mpanzi app.</p>
    """
    html = _wrap_html("Partnership gift received", inner)
    text = strip_tags(inner)
    _send_async("Your partnership gift — Mpanzi Ministries", html, text, to_email)


def send_marketplace_order_email(
    to_email: str,
    *,
    subject: str,
    page_title: str,
    inner_html_paragraphs: list[str],
) -> None:
    """
    HTML transactional email for cart / marketplace orders (async, same thread pattern as auth).
    `inner_html_paragraphs` are trusted HTML fragments (no user HTML; escape caller data).
    """
    inner = "".join(inner_html_paragraphs)
    html = _wrap_marketplace_order_html(page_title, inner)
    text = strip_tags(inner)
    _send_async(subject, html, text, to_email)
