# Ensures pickup_country exists on account_order (idempotent).
# Use when the DB was never migrated with 0035, or the column was dropped manually.

from django.db import migrations


def ensure_pickup_country_column(apps, schema_editor):
    Order = apps.get_model("account", "Order")
    table = Order._meta.db_table
    connection = schema_editor.connection
    qn = connection.ops.quote_name
    col = "pickup_country"

    with connection.cursor() as cursor:
        try:
            existing = {
                c.name for c in connection.introspection.get_table_description(cursor, table)
            }
        except Exception:
            return

    if col in existing:
        return

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


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0035_order_pickup_country"),
    ]

    operations = [
        migrations.RunPython(ensure_pickup_country_column, noop_reverse),
    ]
