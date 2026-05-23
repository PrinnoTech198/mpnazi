"""
Centralized transactional email for authentication flows.

Templates are professional HTML; sending runs on a background thread so API
responses are not blocked by network latency. Delivery uses the Resend HTTP API
(RESEND_API_KEY). SMTP is not used on Railway.
"""

from __future__ import annotations

import logging
import os
import threading

import resend
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape, strip_tags

logger = logging.getLogger(__name__)

# Resend sandbox sender — works without a verified domain (see resend.com/docs).
_RESEND_SANDBOX_FROM = "onboarding@resend.dev"


def _from_email(override: str | None = None) -> str:
    """
    Resolve the sender address for Resend.

    Uses RESEND_FROM_EMAIL when set. Otherwise uses DEFAULT_FROM_EMAIL once the
    domain is verified (RESEND_USE_VERIFIED_DOMAIN=true). Until then, keeps the
    display name from DEFAULT_FROM_EMAIL but sends from onboarding@resend.dev.
    """
    if override:
        return override
    explicit = (os.environ.get("RESEND_FROM_EMAIL") or "").strip()
    if explicit:
        return explicit
    if os.environ.get("RESEND_USE_VERIFIED_DOMAIN", "").lower() in ("1", "true", "yes"):
        return settings.DEFAULT_FROM_EMAIL
    default = (settings.DEFAULT_FROM_EMAIL or "").strip()
    if "<" in default and ">" in default:
        name = default.split("<", 1)[0].strip().strip('"')
        if name:
            return f"{name} <{_RESEND_SANDBOX_FROM}>"
    if default and "@" in default and "<" not in default:
        return f"Mpanzi Ministries <{_RESEND_SANDBOX_FROM}>"
    return f"Mpanzi Ministries <{_RESEND_SANDBOX_FROM}>"


def send_email(
    subject: str,
    message: str,
    from_email: str | None = None,
    recipient_list: list[str] | None = None,
    html_message: str | None = None,
    fail_silently: bool = True,
) -> int:
    """
    Drop-in replacement for ``django.core.mail.send_mail`` using Resend's HTTP API.

    Returns 1 on success, 0 on failure. Logs errors; does not raise when
    ``fail_silently`` is True (default).
    """
    recipients = [str(e).strip() for e in (recipient_list or []) if e and str(e).strip()]
    if not recipients:
        logger.warning("send_email skipped: empty recipient_list subject=%r", subject)
        return 0

    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        logger.error("RESEND_API_KEY is not set; cannot send email subject=%r", subject)
        return 0

    resend.api_key = api_key
    params: resend.Emails.SendParams = {
        "from": _from_email(from_email),
        "to": recipients,
        "subject": subject,
        "text": message or "",
    }
    if html_message:
        params["html"] = html_message

    try:
        resend.Emails.send(params)
        logger.info("Email sent via Resend to=%s subject=%r", recipients, subject)
        return 1
    except Exception:
        logger.exception("Resend send failed to=%s subject=%r", recipients, subject)
        if not fail_silently:
            raise
        return 0


def _send_async(subject: str, html_body: str, text_body: str, to_email: str) -> None:
    def _run() -> None:
        send_email(
            subject=subject,
            message=text_body,
            recipient_list=[to_email],
            html_message=html_body,
            fail_silently=True,
        )

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


def send_verification_email(email: str, code: str, *, expires_minutes: int = 10) -> None:
    inner = f"""
      <p style="margin-top:0;">Thank you for registering. Please verify your email address
      to activate your account.</p>
      <p>Your verification code is:</p>
      <p style="font-size:32px;letter-spacing:10px;font-weight:800;color:#0f172a;
        text-align:center;margin:28px 0;font-variant-numeric:tabular-nums;">
        {code}
      </p>
      <p style="margin-bottom:0;">This code expires in <strong>{expires_minutes} minutes</strong>.
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
      <p><strong>Next steps:</strong> keep this email as your receipt.
      {"You will receive app reminders according to your recurring schedule." if partnership.gift_type == partnership.GIFT_RECURRING else "Our team may follow up about recurring arrangements if you chose recurring giving."}</p>
      <p style="margin-bottom:0;">Questions? Reply to this email or contact us through the Mpanzi app.</p>
    """
    html = _wrap_html("Partnership gift received", inner)
    text = strip_tags(inner)
    _send_async("Your partnership gift — Mpanzi Ministries", html, text, to_email)


def send_cart_order_paid_confirmation(*, order, payment=None) -> None:
    """
    After marketplace cart payment succeeds, email the customer with order line items.
    `order` should be an ``account.models.Order`` (user loaded). ``payment`` is optional
    ``CartOrderPayment`` for reference fields in the email.
    """
    from account.models import Order, OrderItem  # noqa: PLC0415

    assert isinstance(order, Order)

    user = order.user
    to_email = ""
    recipient_name = "Customer"
    if user and getattr(user, "is_active", True):
        to_email = (getattr(user, "email", None) or "").strip()
        full = (user.get_full_name() or "").strip()
        if full:
            recipient_name = full
        elif getattr(user, "username", None):
            recipient_name = str(user.username).strip()

    if not to_email:
        logger.warning(
            "Cart order paid but no recipient email order_id=%s payment_id=%s",
            order.pk,
            getattr(payment, "id", None),
        )
        return

    items = list(
        OrderItem.objects.filter(order_id=order.pk)
        .select_related("service")
        .order_by("pk")
    )

    total = order.total_amount
    total_s = f"{total:.2f}" if hasattr(total, "quantize") else escape(str(total))
    oid = escape(str(order.pk))
    pay_id = escape(str(getattr(payment, "id", "") or ""))
    prov_txn = escape(
        str(
            getattr(payment, "provider_transaction_id", None)
            or getattr(payment, "order_tracking_id", None)
            or order.transaction_id
            or ""
        )
    )

    rows_html = ""
    rows_text_parts: list[str] = []
    if items:
        for line in items:
            svc = line.service
            item_id = escape(str(svc.pk))
            item_name = escape(str(svc.title or "Item"))
            qty = escape(str(line.quantity))
            rows_html += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-variant-numeric:tabular-nums;">{item_id}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{item_name}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:center;">{qty}</td>
        </tr>"""
            rows_text_parts.append(f"  - ID {svc.pk}: {svc.title} x{line.quantity}")
    else:
        rows_html = """
        <tr><td colspan="3" style="padding:12px;color:#64748b;">No line items recorded for this order.</td></tr>"""
        rows_text_parts.append("  (no line items)")

    rep = order.representative
    rep_line = ""
    if rep and (rep.full_name or "").strip():
        rep_line = (
            f'<p style="margin-bottom:0;">Your representative: '
            f"<strong>{escape(rep.full_name.strip())}</strong></p>"
        )

    inner = f"""
      <p style="margin-top:0;">Dear {escape(recipient_name)},</p>
      <p>Thank you for your order with <strong>Mpanzi Ministries</strong>.
      Your payment was received successfully.</p>
      <table role="presentation" cellpadding="0" cellspacing="0"
        style="width:100%;margin:16px 0;border-collapse:separate;border-spacing:0;
        border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Order</td>
            <td style="padding:12px 16px;">#{oid}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Total</td>
            <td style="padding:12px 16px;">TZS {total_s}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Payment reference</td>
            <td style="padding:12px 16px;font-variant-numeric:tabular-nums;">{pay_id or "—"}</td></tr>
        <tr><td style="padding:12px 16px;background:#f8fafc;font-weight:600;color:#0f172a;">Transaction</td>
            <td style="padding:12px 16px;word-break:break-all;">{prov_txn or "—"}</td></tr>
      </table>
      <p style="font-weight:600;color:#0f172a;margin-bottom:8px;">Items in your order</p>
      <table role="presentation" cellpadding="0" cellspacing="0"
        style="width:100%;margin:0 0 20px;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:8px;">
        <thead>
          <tr style="background:#f8fafc;">
            <th style="padding:10px 12px;text-align:left;font-size:13px;color:#0f172a;">Item ID</th>
            <th style="padding:10px 12px;text-align:left;font-size:13px;color:#0f172a;">Item name</th>
            <th style="padding:10px 12px;text-align:center;font-size:13px;color:#0f172a;">Qty</th>
          </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
      </table>
      <p>We will keep you updated as your order moves to your representative and toward pickup.</p>
      {rep_line}
      <p style="margin-bottom:0;">Keep this email as your receipt. Questions? Reply to this email or contact us through the Mpanzi app.</p>
    """
    html = _wrap_marketplace_order_html("Payment received", inner)
    text = (
        f"Dear {recipient_name},\n\n"
        f"Your Mpanzi order #{order.pk} was paid successfully.\n"
        f"Total: TZS {total_s}\n"
        f"Payment reference: {getattr(payment, 'id', '') or '—'}\n"
        f"Transaction: {prov_txn or '—'}\n\n"
        "Items:\n"
        + "\n".join(rows_text_parts)
        + "\n\nThank you for shopping with Mpanzi Ministries."
    )
    _send_async(
        f"Payment received — Mpanzi order #{order.pk}",
        html,
        text,
        to_email,
    )


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
