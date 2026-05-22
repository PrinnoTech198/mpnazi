# Generated manually for prayers app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PrayerRequest",
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
                ("name", models.CharField(blank=True, max_length=100)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("country", models.CharField(max_length=100)),
                ("country_flag", models.CharField(blank=True, max_length=10)),
                ("is_anonymous", models.BooleanField(default=False)),
                ("request_text", models.TextField()),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("general", "General"),
                            ("health", "Health"),
                            ("family", "Family"),
                            ("finance", "Finance"),
                            ("urgent", "Urgent"),
                        ],
                        default="general",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("praying", "Praying"),
                            ("answered", "Answered"),
                            ("urgent", "Urgent"),
                        ],
                        db_index=True,
                        default="new",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("admin_reply", models.TextField(blank=True)),
                ("admin_reply_sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "admin_replied_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="prayer_replies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PrayerAdminNotification",
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
                ("message", models.CharField(max_length=255)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "prayer_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admin_notifications",
                        to="prayers.prayerrequest",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="prayerrequest",
            index=models.Index(
                fields=["status", "-created_at"],
                name="prayers_pra_status_8a0f0d_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="prayerrequest",
            index=models.Index(
                fields=["category", "-created_at"],
                name="prayers_pra_categor_6e8b2a_idx",
            ),
        ),
    ]
