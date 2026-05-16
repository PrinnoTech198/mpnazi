# Generated manually for cart_payment app

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("account", "0030_email_otp_challenge_profile_verified"),
    ]

    operations = [
        migrations.CreateModel(
            name="CartOrderPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="TZS", max_length=3)),
                ("provider", models.CharField(choices=[("AZAMPAY", "AzamPay")], default="AZAMPAY", max_length=32)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("SUCCESS", "Success"), ("FAILED", "Failed")], db_index=True, default="PENDING", max_length=20)),
                ("external_reference", models.CharField(db_index=True, max_length=255, unique=True)),
                ("external_reference_norm", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ("provider_transaction_id", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ("utility_reference", models.CharField(blank=True, max_length=255, null=True)),
                ("raw_initiate_response", models.JSONField(blank=True, null=True)),
                ("raw_last_webhook", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cart_payments", to="account.order")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CartOrderFulfillment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Processing"), ("SENT_TO_REPRESENTATIVE", "Sent to representative"), ("ARRIVED_AT_REPRESENTATIVE", "Arrived at representative"), ("READY_FOR_PICKUP", "Ready for pickup"), ("COMPLETED", "Completed")], db_index=True, default="PENDING", max_length=40)),
                ("internal_note", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="cart_fulfillment", to="account.order")),
            ],
            options={
                "verbose_name": "Cart order fulfillment",
                "verbose_name_plural": "Cart order fulfillments",
            },
        ),
        migrations.CreateModel(
            name="CartPaymentWebhookLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("payload", models.JSONField()),
                ("matched_payment_id", models.IntegerField(blank=True, null=True)),
                ("outcome", models.CharField(blank=True, max_length=120)),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
        migrations.AddIndex(
            model_name="cartorderpayment",
            index=models.Index(fields=["order", "status"], name="cart_pay_order_status_idx"),
        ),
    ]
