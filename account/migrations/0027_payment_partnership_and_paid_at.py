import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0026_alter_eventtestimony_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="partnership",
            name="paid_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="payment",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payments",
                to="account.order",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="partnership",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payments",
                to="account.partnership",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="utility_reference",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=Q(order__isnull=False, partnership__isnull=True)
                | Q(order__isnull=True, partnership__isnull=False),
                name="account_payment_order_xor_partnership",
            ),
        ),
    ]
