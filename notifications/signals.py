from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from account.models import Book, Devotional, Event, News, Sermon, Service

from .fcm import all_device_tokens

logger = logging.getLogger(__name__)


def _enqueue(title: str, body: str, data: dict[str, Any]) -> None:
    tokens = all_device_tokens()
    if not tokens:
        logger.debug("No device tokens registered; skip push: %s", title)
        return
    try:
        from django_q.tasks import async_task

        async_task(
            "notifications.tasks.deliver_push_task",
            tokens,
            title,
            body,
            data,
        )
    except Exception:
        logger.exception("Failed to enqueue push notification task")


def _payload(type_: str, pk: int, route: str) -> dict[str, Any]:
    return {
        "type": type_,
        "id": str(pk),
        "route": route,
    }


@receiver(post_save, sender=Sermon)
def sermon_created_notify(sender, instance, created, **kwargs):
    if not created:
        return
    route = f"/sermons/{instance.pk}"
    _enqueue(
        "New Sermon 🎙️",
        (instance.title or "New sermon")[:500],
        _payload("sermon", instance.pk, route),
    )


@receiver(post_save, sender=Devotional)
def devotional_created_notify(sender, instance, created, **kwargs):
    if not created:
        return
    route = f"/devotionals/{instance.pk}"
    _enqueue(
        "New Devotional 📖",
        (instance.title or "New devotional")[:500],
        _payload("devotional", instance.pk, route),
    )


@receiver(post_save, sender=Event)
def event_created_notify(sender, instance, created, **kwargs):
    if not created:
        return
    et = (instance.event_type or "crusade").strip().lower()
    if et == "crusade":
        route = f"/crusades/{instance.pk}"
    else:
        route = f"/events/{et}/{instance.pk}"
    _enqueue(
        "New Event 🌍",
        (instance.title or "New event")[:500],
        _payload("event", instance.pk, route),
    )


@receiver(post_save, sender=Book)
def book_created_notify(sender, instance, created, **kwargs):
    if not created:
        return
    route = f"/library/{instance.pk}"
    _enqueue(
        "New Book 📚",
        (instance.title or "New book")[:500],
        _payload("book", instance.pk, route),
    )


@receiver(post_save, sender=News)
def news_created_notify(sender, instance, created, **kwargs):
    if not created:
        return
    route = f"/news/{instance.pk}"
    _enqueue(
        "Breaking News 📰",
        (instance.title or "Breaking news")[:500],
        _payload("news", instance.pk, route),
    )


@receiver(post_save, sender=Service)
def service_created_notify(sender, instance, created, **kwargs):
    """
    Marketplace service catalog entry. This codebase has no separate Item / Product models;
    both requested flows map to Service (route /services/{id}).
    """
    if not created:
        return
    route = f"/services/{instance.pk}"
    _enqueue(
        "New Service ✨",
        (instance.title or "New service")[:500],
        _payload("service", instance.pk, route),
    )
