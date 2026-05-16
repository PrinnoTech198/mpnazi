from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0036_ensure_order_pickup_country_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="partnership",
            name="guest_email",
            field=models.EmailField(
                blank=True,
                null=True,
                max_length=254,
                help_text="For anonymous partner giving; receipts go here.",
            ),
        ),
    ]
