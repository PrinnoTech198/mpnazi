"""Mark very old pending cart MNO attempts as FAILED (does not touch partner payments)."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from cart_payment.models import CartOrderPayment


class Command(BaseCommand):
    help = "Expire stale PENDING cart_order_payments (default: older than 24h)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)

    def handle(self, *args, **options):
        hours = max(1, int(options["hours"]))
        cutoff = timezone.now() - timedelta(hours=hours)
        qs = CartOrderPayment.objects.filter(
            status=CartOrderPayment.STATUS_PENDING,
            created_at__lt=cutoff,
        )
        n = qs.update(status=CartOrderPayment.STATUS_FAILED, completed_at=timezone.now())
        self.stdout.write(self.style.SUCCESS(f"Updated {n} stale cart payment(s)."))
