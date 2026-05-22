# Generated manually — one TransactionHistory row per payment.

from django.db import migrations, models


def dedupe_transaction_history(apps, schema_editor):
    TransactionHistory = apps.get_model("payments", "TransactionHistory")
    groups: dict[tuple[str, int], list] = {}
    for tx in TransactionHistory.objects.order_by("id"):
        key = (tx.payment_kind, tx.payment_id)
        groups.setdefault(key, []).append(tx)

    for rows in groups.values():
        if len(rows) <= 1:
            continue
        keep = rows[0]
        latest = rows[-1]
        keep.to_status = latest.to_status
        keep.provider = latest.provider
        keep.note = latest.note or keep.note
        if latest.merchant_reference:
            keep.merchant_reference = latest.merchant_reference
        if latest.order_tracking_id:
            keep.order_tracking_id = latest.order_tracking_id
        if latest.amount is not None:
            keep.amount = latest.amount
        if latest.currency:
            keep.currency = latest.currency
        if latest.raw_provider_response:
            keep.raw_provider_response = latest.raw_provider_response
        keep.save()
        for extra in rows[1:]:
            extra.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="transactionhistory",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(dedupe_transaction_history, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="transactionhistory",
            constraint=models.UniqueConstraint(
                fields=("payment_kind", "payment_id"),
                name="payments_txhistory_kind_payment_uniq",
            ),
        ),
    ]
