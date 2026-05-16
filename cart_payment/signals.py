from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from account.models import Order

from .models import CartOrderFulfillment
from .order_notifications import maybe_notify_fulfillment_status_change


@receiver(pre_save, sender=CartOrderFulfillment)
def _cart_fulfillment_cache_previous_status(
    sender, instance: CartOrderFulfillment, **kwargs
) -> None:
    if not instance.pk:
        instance._mpanzi_ff_prev_status = None
        return
    try:
        instance._mpanzi_ff_prev_status = CartOrderFulfillment.objects.only(
            "status"
        ).get(pk=instance.pk).status
    except CartOrderFulfillment.DoesNotExist:
        instance._mpanzi_ff_prev_status = None


@receiver(post_save, sender=CartOrderFulfillment)
def _cart_fulfillment_email_on_status_change(
    sender, instance: CartOrderFulfillment, **kwargs
) -> None:
    previous = getattr(instance, "_mpanzi_ff_prev_status", None)
    current = instance.status
    if previous == current:
        return
    order = Order.objects.select_related("user", "representative").filter(
        pk=instance.order_id
    ).first()
    if not order:
        return
    maybe_notify_fulfillment_status_change(
        order, previous=previous, current=current
    )
