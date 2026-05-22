"""Verify Pesapal sandbox credentials: python manage.py pesapal_test_auth"""
from django.core.management.base import BaseCommand

from payments.providers.pesapal import (
    PesapalConfigurationError,
    PesapalProvider,
    clear_pesapal_cache,
)


class Command(BaseCommand):
    help = "Request a Pesapal API token using PESAPAL_CONSUMER_KEY / SECRET from settings."

    def handle(self, *args, **options):
        try:
            clear_pesapal_cache()
            provider = PesapalProvider()
            token = provider._token()
            self.stdout.write(self.style.SUCCESS(f"OK — token received ({len(token)} chars)"))
        except PesapalConfigurationError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            raise SystemExit(1)
