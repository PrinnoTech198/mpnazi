# Generated manually for Pesapal integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cart_payment", "0002_rename_cart_pay_order_status_idx_cart_paymen_order_i_e33ea4_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartorderpayment",
            name="checkout_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="cartorderpayment",
            name="metadata",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cartorderpayment",
            name="order_tracking_id",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="cartorderpayment",
            name="payment_method",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="cartorderpayment",
            name="provider",
            field=models.CharField(
                choices=[
                    ("AZAMPAY", "AzamPay (legacy)"),
                    ("PESAPAL", "Pesapal"),
                ],
                default="PESAPAL",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="cartorderpayment",
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
                db_index=True,
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
