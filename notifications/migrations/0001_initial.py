# Generated manually for notifications app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, max_length=512, unique=True)),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS")], max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="device_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="NotificationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, max_length=512)),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField(blank=True)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("sent", "Sent"), ("failed", "Failed")], db_index=True, max_length=16)),
                ("error_message", models.TextField(blank=True)),
                ("fcm_message_id", models.CharField(blank=True, max_length=512)),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-sent_at"],
            },
        ),
    ]
