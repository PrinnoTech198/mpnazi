# Generated manually for Pesapal integration

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PaymentProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(choices=[("PESAPAL", "Pesapal"), ("STRIPE", "Stripe"), ("PAYPAL", "PayPal"), ("FLUTTERWAVE", "Flutterwave"), ("AZAMPAY", "AzamPay (legacy)")], max_length=32, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="PaymentWebhookLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("pesapal_ipn", "Pesapal IPN"), ("azampay_legacy", "AzamPay legacy")], default="pesapal_ipn", max_length=40)),
                ("payment_kind", models.CharField(choices=[("partnership", "Partner giving"), ("cart", "Cart checkout"), ("unknown", "Unknown")], default="unknown", max_length=20)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("payload", models.JSONField()),
                ("merchant_reference", models.CharField(blank=True, db_index=True, max_length=255)),
                ("order_tracking_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("matched_payment_id", models.IntegerField(blank=True, null=True)),
                ("matched_cart_payment_id", models.IntegerField(blank=True, null=True)),
                ("outcome", models.CharField(blank=True, max_length=120)),
                ("http_status_returned", models.IntegerField(default=200)),
            ],
            options={"ordering": ["-received_at"]},
        ),
        migrations.CreateModel(
            name="TransactionHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_kind", models.CharField(max_length=20)),
                ("payment_id", models.IntegerField(db_index=True)),
                ("provider", models.CharField(max_length=32)),
                ("from_status", models.CharField(blank=True, max_length=20)),
                ("to_status", models.CharField(max_length=20)),
                ("order_tracking_id", models.CharField(blank=True, max_length=255)),
                ("merchant_reference", models.CharField(blank=True, max_length=255)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("raw_provider_response", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "Transaction histories",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="paymentwebhooklog",
            index=models.Index(fields=["source", "received_at"], name="payments_pa_source_6e0b0d_idx"),
        ),
    ]
