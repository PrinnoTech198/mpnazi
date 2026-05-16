# Pickup columns may already exist on account_order (NOT NULL) outside repo migrations.

from django.db import migrations, models

_PICKUP_COLS = (
    "pickup_region",
    "pickup_district",
    "pickup_ward",
    "pickup_village",
    "pickup_landmark",
)


def ensure_pickup_columns(apps, schema_editor):
    Order = apps.get_model("account", "Order")
    table = Order._meta.db_table
    connection = schema_editor.connection
    qn = connection.ops.quote_name

    with connection.cursor() as cursor:
        try:
            existing = {c.name for c in connection.introspection.get_table_description(cursor, table)}
        except Exception:
            return

    for col in _PICKUP_COLS:
        if col in existing:
            continue
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {qn(col)} VARCHAR(255) NOT NULL DEFAULT %s",
                    [""],
                )
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ALTER COLUMN {qn(col)} DROP DEFAULT"
                )
            elif connection.vendor == "sqlite":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} VARCHAR(255) NOT NULL DEFAULT ''"
                )
            elif connection.vendor == "mysql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} VARCHAR(255) NOT NULL DEFAULT ''"
                )
            else:
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} VARCHAR(255) NOT NULL DEFAULT ''"
                )

    with connection.cursor() as cursor:
        for col in _PICKUP_COLS:
            if col not in existing:
                continue
            if connection.vendor == "postgresql":
                cursor.execute(
                    f"UPDATE {qn(table)} SET {qn(col)} = %s WHERE {qn(col)} IS NULL",
                    [""],
                )
            elif connection.vendor == "mysql":
                cursor.execute(
                    f"UPDATE {qn(table)} SET {col} = '' WHERE {col} IS NULL"
                )
            else:
                cursor.execute(
                    f"UPDATE {qn(table)} SET {col} = '' WHERE {col} IS NULL"
                )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0032_order_fulfillment_status"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="order",
                    name="pickup_region",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="order",
                    name="pickup_district",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="order",
                    name="pickup_ward",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="order",
                    name="pickup_village",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="order",
                    name="pickup_landmark",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_pickup_columns, noop_reverse),
            ],
        ),
    ]
