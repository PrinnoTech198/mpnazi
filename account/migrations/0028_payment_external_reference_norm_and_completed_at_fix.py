from django.db import migrations, models


def backfill_external_reference_norm(apps, schema_editor):
    Payment = apps.get_model("account", "Payment")
    qs = Payment.objects.exclude(external_reference__isnull=True).exclude(external_reference="")
    for p in qs.iterator(chunk_size=500):
        ref = (p.external_reference or "").strip()
        norm = "".join(c for c in ref.lower() if c.isalnum())
        if norm:
            Payment.objects.filter(pk=p.pk).update(external_reference_norm=norm)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0027_payment_partnership_and_paid_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="external_reference_norm",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.RunPython(backfill_external_reference_norm, noop_reverse),
    ]
