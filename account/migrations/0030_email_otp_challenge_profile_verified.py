# Generated manually for auth OTP + email verification

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_email_verified_for_active_users(apps, schema_editor):
    Profile = apps.get_model("account", "Profile")
    for profile in Profile.objects.filter(email_verified_at__isnull=True).iterator():
        u = profile.user
        if getattr(u, "is_active", False):
            profile.email_verified_at = timezone.now()
            profile.save(update_fields=["email_verified_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0029_payment_completed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="EmailOTPChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("purpose", models.CharField(choices=[("registration", "Registration"), ("password_reset", "Password reset")], db_index=True, max_length=32)),
                ("code_hash", models.CharField(max_length=128)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="email_otp_challenges",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="emailotpchallenge",
            index=models.Index(
                fields=["user", "purpose", "used_at"],
                name="acct_eotp_user_purp_used",
            ),
        ),
        migrations.RunPython(backfill_email_verified_for_active_users, noop_reverse),
    ]
