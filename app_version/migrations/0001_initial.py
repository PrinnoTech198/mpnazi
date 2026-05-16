# Generated manually for app_version

import app_version.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AppVersionControl",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "latest_version",
                    models.CharField(
                        help_text="Latest published app version (e.g. 2.1.0).",
                        max_length=32,
                        validators=[app_version.models.validate_semver],
                    ),
                ),
                (
                    "minimum_supported_version",
                    models.CharField(
                        help_text="Oldest version still allowed to use the app.",
                        max_length=32,
                        validators=[app_version.models.validate_semver],
                    ),
                ),
                (
                    "update_type",
                    models.CharField(
                        choices=[
                            ("optional", "Optional"),
                            ("recommended", "Recommended"),
                            ("force", "Force"),
                        ],
                        default="optional",
                        max_length=16,
                    ),
                ),
                (
                    "title",
                    models.CharField(default="Update Available", max_length=120),
                ),
                (
                    "message",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Shown in update dialogs.",
                    ),
                ),
                (
                    "playstore_url",
                    models.URLField(
                        help_text="Google Play Store listing URL.",
                        max_length=512,
                    ),
                ),
                (
                    "payment_force_update",
                    models.BooleanField(
                        default=False,
                        help_text="Block payment/checkout flows when app version is below minimum.",
                    ),
                ),
                (
                    "maintenance_mode",
                    models.BooleanField(
                        default=False,
                        help_text="When enabled, the app shows a global maintenance screen.",
                    ),
                ),
                ("maintenance_message", models.TextField(blank=True, default="")),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Only one active configuration is allowed at a time.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "App version control",
                "verbose_name_plural": "App version controls",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="appversioncontrol",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("is_active",),
                name="unique_active_app_version_control",
            ),
        ),
    ]
