from django.apps import AppConfig


class CartPaymentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cart_payment"
    verbose_name = "Cart checkout payments"

    def ready(self) -> None:
        from . import signals  # noqa: F401
