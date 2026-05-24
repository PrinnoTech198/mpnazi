from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import models
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def validate_semver(value: str) -> None:
    if not SEMVER_RE.match((value or "").strip()):
        raise ValidationError(
            "Version must be semantic (e.g. 2.1.0).",
            code="invalid_semver",
        )


class AppVersionControl(models.Model):
    UPDATE_OPTIONAL = "optional"
    UPDATE_RECOMMENDED = "recommended"
    UPDATE_FORCE = "force"

    UPDATE_TYPE_CHOICES = [
        (UPDATE_OPTIONAL, "Optional"),
        (UPDATE_RECOMMENDED, "Recommended"),
        (UPDATE_FORCE, "Force"),
    ]

    latest_version = models.CharField(
        max_length=32,
        validators=[validate_semver],
        help_text="Latest published app version (e.g. 2.1.0).",
    )
    minimum_supported_version = models.CharField(
        max_length=32,
        validators=[validate_semver],
        help_text="Oldest version still allowed to use the app.",
    )
    update_type = models.CharField(
        max_length=16,
        choices=UPDATE_TYPE_CHOICES,
        default=UPDATE_OPTIONAL,
    )
    title = models.CharField(max_length=120, default="Update Available")
    message = models.TextField(
        blank=True,
        default="",
        help_text="Shown in update dialogs.",
    )
    playstore_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="Google Play Store listing URL.",
    )
    payment_force_update = models.BooleanField(
        default=False,
        help_text="Block payment/checkout flows when app version is below minimum.",
    )
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="When enabled, the app shows a global maintenance screen.",
    )
    maintenance_message = models.TextField(blank=True, default="")
    is_active = models.BooleanField(
        default=True,
        help_text="Only one active configuration is allowed at a time.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "App version control"
        verbose_name_plural = "App version controls"

    def __str__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"v{self.latest_version} ({self.update_type}, {status})"

    def clean(self) -> None:
        super().clean()
        latest = (self.latest_version or "").strip()
        minimum = (self.minimum_supported_version or "").strip()
        if not latest or not minimum:
            return
        if not SEMVER_RE.match(latest) or not SEMVER_RE.match(minimum):
            return
        if _compare_semver(minimum, latest) > 0:
            raise ValidationError(
                {
                    "minimum_supported_version": (
                        "Minimum supported version cannot be greater than latest version."
                    ),
                }
            )

    def save(self, *args, **kwargs):
        if self.is_active:
            AppVersionControl.objects.filter(is_active=True).exclude(
                pk=self.pk
            ).update(is_active=False)
        super().save(*args, **kwargs)


def _parse_semver_parts(value: str) -> list[int] | None:
    text = (value or "").strip()
    if not SEMVER_RE.match(text):
        return None
    return [int(x) for x in text.split(".")]


def _compare_semver(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b. Requires valid semver strings."""
    pa = _parse_semver_parts(a)
    pb = _parse_semver_parts(b)
    if pa is None or pb is None:
        raise ValidationError("Invalid semantic version.")
    for i in range(3):
        if pa[i] < pb[i]:
            return -1
        if pa[i] > pb[i]:
            return 1
    return 0
