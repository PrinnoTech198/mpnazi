# Generated manually for Pesapal integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0039_alter_event_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="checkout_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="currency",
            field=models.CharField(blank=True, default="TZS", max_length=3),
        ),
        migrations.AddField(
            model_name="payment",
            name="metadata",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="order_tracking_id",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="payment_method",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="payment",
            name="provider",
            field=models.CharField(
                choices=[
                    ("AZAMPAY", "AzamPay (legacy)"),
                    ("PESAPAL", "Pesapal"),
                ],
                default="PESAPAL",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("PROCESSING", "Processing"),
                    ("SUCCESS", "Success"),
                    ("FAILED", "Failed"),
                    ("CANCELLED", "Cancelled"),
                    ("REFUNDED", "Refunded"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
