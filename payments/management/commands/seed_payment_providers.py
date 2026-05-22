"""Seed default payment provider rows."""
from django.core.management.base import BaseCommand

from payments.models import PaymentProvider


class Command(BaseCommand):
    help = "Create PaymentProvider rows (Pesapal default, legacy AzamPay, future stubs)."

    def handle(self, *args, **options):
        specs = [
            ("PESAPAL", "Pesapal", True, True),
            ("STRIPE", "Stripe", False, False),
            ("PAYPAL", "PayPal", False, False),
            ("FLUTTERWAVE", "Flutterwave", False, False),
            ("AZAMPAY", "AzamPay (legacy)", False, False),
        ]
        for code, name, active, default in specs:
            PaymentProvider.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "is_active": active,
                    "is_default": default,
                },
            )
        self.stdout.write(self.style.SUCCESS("Payment providers seeded."))
