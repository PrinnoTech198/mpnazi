"""
Re-sync a stuck partner or cart payment from Pesapal GetTransactionStatus.

Example:
  python manage.py pesapal_resync_payment --partner-payment-id 46
  python manage.py pesapal_resync_payment --cart-payment-id 12
"""
from django.core.management.base import BaseCommand

from account.models import Payment
from cart_payment.models import CartOrderPayment
from payments.services.payment_service import PaymentService


class Command(BaseCommand):
    help = "Fetch Pesapal status and update local payment + partnership/order."

    def add_arguments(self, parser):
        parser.add_argument("--partner-payment-id", type=int, default=None)
        parser.add_argument("--cart-payment-id", type=int, default=None)

    def handle(self, *args, **options):
        svc = PaymentService()
        pid = options.get("partner_payment_id")
        cid = options.get("cart_payment_id")

        if pid:
            pay = Payment.objects.filter(pk=pid, partnership__isnull=False).first()
            if not pay:
                self.stderr.write(self.style.ERROR(f"Partner payment {pid} not found"))
                raise SystemExit(1)
            before = pay.status
            pay = svc.verify_and_sync_partner_payment(pay)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Partner payment {pid}: {before} -> {pay.status} "
                    f"ref={pay.external_reference!r} tracking={pay.order_tracking_id!r}"
                )
            )
            return

        if cid:
            pay = CartOrderPayment.objects.filter(pk=cid).first()
            if not pay:
                self.stderr.write(self.style.ERROR(f"Cart payment {cid} not found"))
                raise SystemExit(1)
            before = pay.status
            pay = svc.verify_and_sync_cart_payment(pay)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cart payment {cid}: {before} -> {pay.status} "
                    f"ref={pay.external_reference!r} tracking={pay.order_tracking_id!r}"
                )
            )
            return

        self.stderr.write("Provide --partner-payment-id or --cart-payment-id")
        raise SystemExit(1)
