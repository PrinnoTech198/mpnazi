from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0040_payment_pesapal_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="partnership",
            name="last_reminder_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="partnership",
            name="next_reminder_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
