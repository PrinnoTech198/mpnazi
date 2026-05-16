# fulfillment_status may already exist on account_order (NOT NULL) outside repo migrations.

from django.db import migrations, models


def add_fulfillment_status_if_needed(apps, schema_editor):
    Order = apps.get_model("account", "Order")
    table = Order._meta.db_table
    connection = schema_editor.connection
    qn = connection.ops.quote_name

    with connection.cursor() as cursor:
        try:
            cols = [c.name for c in connection.introspection.get_table_description(cursor, table)]
        except Exception:
            return
        if "fulfillment_status" in cols:
            if connection.vendor == "postgresql":
                cursor.execute(
                    f"UPDATE {qn(table)} SET {qn('fulfillment_status')} = %s "
                    f"WHERE {qn('fulfillment_status')} IS NULL",
                    ["PENDING"],
                )
            elif connection.vendor == "sqlite":
                cursor.execute(
                    f"UPDATE {qn(table)} SET fulfillment_status = 'PENDING' "
                    "WHERE fulfillment_status IS NULL"
                )
            elif connection.vendor == "mysql":
                cursor.execute(
                    f"UPDATE {qn(table)} SET fulfillment_status = 'PENDING' "
                    "WHERE fulfillment_status IS NULL"
                )
            return

    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN {qn('fulfillment_status')} "
                f"VARCHAR(40) NOT NULL DEFAULT %s",
                ["PENDING"],
            )
            cursor.execute(
                f"ALTER TABLE {qn(table)} ALTER COLUMN {qn('fulfillment_status')} DROP DEFAULT"
            )
        elif connection.vendor == "sqlite":
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN fulfillment_status "
                f"VARCHAR(40) NOT NULL DEFAULT 'PENDING'"
            )
        elif connection.vendor == "mysql":
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN fulfillment_status "
                "VARCHAR(40) NOT NULL DEFAULT 'PENDING'"
            )
        else:
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN fulfillment_status "
                "VARCHAR(40) NOT NULL DEFAULT 'PENDING'"
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0031_order_customer_note"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="order",
                    name="fulfillment_status",
                    field=models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("SENT_TO_REPRESENTATIVE", "Sent to representative"),
                            ("ARRIVED_AT_REPRESENTATIVE", "Arrived at representative"),
                            ("READY_FOR_PICKUP", "Ready for pickup"),
                            ("COMPLETED", "Completed"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=40,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_fulfillment_status_if_needed, noop_reverse),
            ],
        ),
    ]
