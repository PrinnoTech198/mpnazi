# One PaymentWebhookLog row per matched payment (merge IPN + status poll).

from django.db import migrations, models


def _outcome_rank(outcome: str) -> int:
    o = (outcome or "").strip().lower()
    if o == "success":
        return 100
    if o == "failed":
        return 90
    if o.startswith("status_error"):
        return 85
    if o == "still_pending":
        return 50
    if o in ("idempotent_skip", "idempotent_skip_locked"):
        return 40
    if o.startswith("matched:"):
        return 25
    if o == "received":
        return 15
    return 20


def dedupe_payment_webhook_logs(apps, schema_editor):
    PaymentWebhookLog = apps.get_model("payments", "PaymentWebhookLog")
    groups: dict[tuple[str, int], list] = {}

    for log in PaymentWebhookLog.objects.order_by("id"):
        pid = None
        if log.payment_kind == "partnership" and log.matched_payment_id:
            pid = log.matched_payment_id
        elif log.payment_kind == "cart" and log.matched_cart_payment_id:
            pid = log.matched_cart_payment_id
        if pid is None:
            continue
        groups.setdefault((log.payment_kind, pid), []).append(log)

    for rows in groups.values():
        if len(rows) <= 1:
            continue
        keep = rows[0]
        best_outcome = keep.outcome or ""
        best_rank = _outcome_rank(best_outcome)
        merged_payload = keep.payload if isinstance(keep.payload, dict) else {}

        for row in rows[1:]:
            rank = _outcome_rank(row.outcome or "")
            if rank > best_rank:
                best_rank = rank
                best_outcome = row.outcome
            incoming = row.payload if isinstance(row.payload, dict) else {}
            if incoming:
                merged_payload = {**merged_payload, **incoming}
            if row.order_tracking_id and not keep.order_tracking_id:
                keep.order_tracking_id = row.order_tracking_id
            if row.merchant_reference and not keep.merchant_reference:
                keep.merchant_reference = row.merchant_reference
            if row.source == "pesapal_ipn":
                keep.source = row.source

        keep.outcome = best_outcome
        keep.payload = merged_payload
        keep.save()
        for row in rows[1:]:
            row.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_transactionhistory_one_per_payment"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentwebhooklog",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(dedupe_payment_webhook_logs, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="paymentwebhooklog",
            constraint=models.UniqueConstraint(
                condition=models.Q(matched_payment_id__isnull=False),
                fields=("payment_kind", "matched_payment_id"),
                name="payments_webhooklog_partner_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentwebhooklog",
            constraint=models.UniqueConstraint(
                condition=models.Q(matched_cart_payment_id__isnull=False),
                fields=("payment_kind", "matched_cart_payment_id"),
                name="payments_webhooklog_cart_uniq",
            ),
        ),
    ]
