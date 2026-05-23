from django.conf import settings
from django.db import migrations, models


def backfill_emailotp_email(apps, schema_editor):
    EmailOTPChallenge = apps.get_model("account", "EmailOTPChallenge")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    for ch in EmailOTPChallenge.objects.filter(email="").select_related("user").iterator():
        user = ch.user_id and User.objects.filter(pk=ch.user_id).first()
        if user:
            ch.email = (user.email or user.username or "").strip()
            ch.save(update_fields=["email"])


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0041_partnership_recurring_reminders"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailotpchallenge",
            name="email",
            field=models.EmailField(blank=True, db_index=True),
        ),
        migrations.AddField(
            model_name="emailotpchallenge",
            name="verification_code",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name="emailotpchallenge",
            name="status_code",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("used", "Used"),
                    ("expired", "Expired"),
                    ("locked", "Locked"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="emailotpchallenge",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="email_otp_challenges",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_emailotp_email, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="emailotpchallenge",
            index=models.Index(
                fields=["email", "purpose", "status_code"],
                name="acct_eotp_email_purp_st",
            ),
        ),
    ]
