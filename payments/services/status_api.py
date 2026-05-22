"""
Build consistent status API responses after Pesapal verification.
Never expose FAILED to clients until the provider confirms a terminal failure.
"""
from __future__ import annotations

from account.models import Order, Payment
from cart_payment.models import CartOrderPayment
from payments.providers.base import PaymentStatusResult
from payments.services.payment_service import PaymentService

_PAYMENT_FAILED = Payment.STATUS_FAILED
_CART_FAILED = CartOrderPayment.STATUS_FAILED


def pesapal_is_confirmed_success(result: PaymentStatusResult) -> bool:
    return result.status == "completed"


def pesapal_is_confirmed_failure(result: PaymentStatusResult) -> bool:
    """Only true when Pesapal reports a definitive failed/reversed payment."""
    if result.status == "completed":
        return False
    code = result.provider_status_code
    desc = (result.provider_status_description or "").strip().upper()
    if code == 1 or desc in ("COMPLETED", "COMPLETE"):
        return False
    if code == 2 or desc == "FAILED":
        return True
    if code == 3 or desc == "REVERSED":
        return True
    # status_code 0 / INVALID is inconclusive — keep processing
    if code == 0 or desc == "INVALID":
        return False
    return result.status in ("failed", "cancelled", "refunded")


def _map_local_to_api_status(local_status: str, *, provider_failed: bool, provider_success: bool) -> str:
    if provider_success or local_status == Payment.STATUS_SUCCESS:
        return "SUCCESS"
    if local_status == Payment.STATUS_CANCELLED:
        return "CANCELLED"
    if local_status in (_PAYMENT_FAILED, _CART_FAILED):
        return "FAILED" if provider_failed else "PROCESSING"
    if local_status == Payment.STATUS_PENDING:
        return "PENDING"
    return "PROCESSING"


def build_partner_status_payload(payment: Payment) -> dict:
    """Sync with Pesapal when possible, then return client-safe status."""
    provider_success = False
    provider_failed = False
    provider_pending = True

    if payment.status != Payment.STATUS_SUCCESS:
        tracking = payment.order_tracking_id or payment.provider_transaction_id
        if tracking:
            try:
                payment = PaymentService().verify_and_sync_partner_payment(payment)
            except Exception:
                pass

    tracking = payment.order_tracking_id or payment.provider_transaction_id
    if tracking and payment.status != Payment.STATUS_SUCCESS:
        try:
            pr = PaymentService().provider.get_transaction_status(tracking)
            provider_success = pesapal_is_confirmed_success(pr)
            provider_failed = pesapal_is_confirmed_failure(pr)
            provider_pending = not provider_success and not provider_failed
            if provider_success and payment.status != Payment.STATUS_SUCCESS:
                payment = PaymentService().verify_and_sync_partner_payment(payment)
            elif provider_failed and payment.status not in (
                Payment.STATUS_SUCCESS,
                Payment.STATUS_FAILED,
            ):
                PaymentService().verify_and_sync_partner_payment(payment)
                payment.refresh_from_db()
        except Exception:
            provider_pending = True

    api_status = _map_local_to_api_status(
        payment.status,
        provider_failed=provider_failed,
        provider_success=provider_success,
    )
    verified = (
        api_status == "SUCCESS"
        and (provider_success or payment.status == Payment.STATUS_SUCCESS)
    ) or (
        api_status == "FAILED"
        and provider_failed
        and payment.status == Payment.STATUS_FAILED
    ) or api_status == "CANCELLED"

    base = {
        "payment_id": payment.id,
        "partnership_id": payment.partnership_id,
        "external_reference": payment.external_reference,
        "transaction_id": payment.provider_transaction_id,
        "order_tracking_id": payment.order_tracking_id,
        "checkout_url": payment.checkout_url or "",
        "local_status": payment.status,
        "verified": verified,
        "provider_pending": provider_pending,
    }

    if api_status == "SUCCESS":
        return {
            **base,
            "success": True,
            "status": "SUCCESS",
            "message": "Payment successful",
        }
    if api_status == "FAILED":
        return {
            **base,
            "success": False,
            "status": "FAILED",
            "message": "Payment failed",
            "verified": True,
        }
    if api_status == "CANCELLED":
        return {
            **base,
            "success": False,
            "status": "CANCELLED",
            "message": "Payment cancelled",
            "verified": True,
        }
    if api_status == "PENDING":
        return {
            **base,
            "success": False,
            "status": "PENDING",
            "message": "Payment not started yet. Open checkout to pay.",
        }
    return {
        **base,
        "success": False,
        "status": "PROCESSING",
        "message": "Waiting for payment confirmation. Complete payment on Pesapal if you have not already.",
    }


def build_cart_status_payload(pay: CartOrderPayment) -> dict:
    order = pay.order
    provider_success = False
    provider_failed = False
    provider_pending = True

    if pay.status != CartOrderPayment.STATUS_SUCCESS:
        tracking = pay.order_tracking_id or pay.provider_transaction_id
        if tracking:
            try:
                pay = PaymentService().verify_and_sync_cart_payment(pay)
                order = pay.order
            except Exception:
                pass

    tracking = pay.order_tracking_id or pay.provider_transaction_id
    if tracking and pay.status != CartOrderPayment.STATUS_SUCCESS:
        try:
            pr = PaymentService().provider.get_transaction_status(tracking)
            provider_success = pesapal_is_confirmed_success(pr)
            provider_failed = pesapal_is_confirmed_failure(pr)
            provider_pending = not provider_success and not provider_failed
            if provider_success and pay.status != CartOrderPayment.STATUS_SUCCESS:
                pay = PaymentService().verify_and_sync_cart_payment(pay)
                order = pay.order
            elif provider_failed:
                pay = PaymentService().verify_and_sync_cart_payment(pay)
                order = pay.order
        except Exception:
            provider_pending = True

    api_status = _map_local_to_api_status(
        pay.status,
        provider_failed=provider_failed and pay.status == CartOrderPayment.STATUS_FAILED,
        provider_success=provider_success or pay.status == CartOrderPayment.STATUS_SUCCESS,
    )
    verified = (
        (api_status == "SUCCESS" or order.status == Order.STATUS_PAID)
        and (provider_success or pay.status == CartOrderPayment.STATUS_SUCCESS)
    ) or (
        api_status == "FAILED"
        and provider_failed
        and pay.status == CartOrderPayment.STATUS_FAILED
    ) or api_status == "CANCELLED"

    from cart_payment.models import CartOrderFulfillment

    ff = CartOrderFulfillment.objects.filter(order=order).first()
    fulfillment = ff.status if ff else order.fulfillment_status

    base = {
        "payment_id": pay.id,
        "order_id": pay.order_id,
        "external_reference": pay.external_reference,
        "transaction_id": pay.provider_transaction_id or "",
        "order_tracking_id": pay.order_tracking_id or "",
        "checkout_url": pay.checkout_url or "",
        "order_status": order.status,
        "fulfillment_status": fulfillment,
        "local_status": pay.status,
        "verified": verified,
        "provider_pending": provider_pending,
    }

    if api_status == "SUCCESS" or order.status == Order.STATUS_PAID:
        return {
            **base,
            "success": True,
            "status": "SUCCESS",
            "message": "Payment successful",
            "order_status": order.status,
        }
    if api_status == "FAILED":
        return {
            **base,
            "success": False,
            "status": "FAILED",
            "message": "Payment failed",
            "verified": True,
        }
    if api_status == "CANCELLED":
        return {
            **base,
            "success": False,
            "status": "CANCELLED",
            "message": "Payment cancelled",
            "verified": True,
        }
    return {
        **base,
        "success": False,
        "status": "PROCESSING",
        "message": "Waiting for payment confirmation. Complete payment on Pesapal if you have not already.",
    }
