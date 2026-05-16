# duration_hours / line_note may already exist on account_orderitem (NOT NULL).

from django.db import migrations, models


def ensure_orderitem_columns(apps, schema_editor):
    OrderItem = apps.get_model("account", "OrderItem")
    table = OrderItem._meta.db_table
    connection = schema_editor.connection
    qn = connection.ops.quote_name

    with connection.cursor() as cursor:
        try:
            existing = {c.name for c in connection.introspection.get_table_description(cursor, table)}
        except Exception:
            return

    def _add_int_col(col: str):
        if col in existing:
            return
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {qn(col)} INTEGER NOT NULL DEFAULT 1"
                )
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ALTER COLUMN {qn(col)} DROP DEFAULT"
                )
            elif connection.vendor == "sqlite":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} INTEGER NOT NULL DEFAULT 1"
                )
            elif connection.vendor == "mysql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} INT NOT NULL DEFAULT 1"
                )
            else:
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} INTEGER NOT NULL DEFAULT 1"
                )

    def _add_text_col(col: str):
        if col in existing:
            return
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {qn(col)} TEXT NOT NULL DEFAULT %s",
                    [""],
                )
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ALTER COLUMN {qn(col)} DROP DEFAULT"
                )
            elif connection.vendor == "sqlite":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
                )
            elif connection.vendor == "mysql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} LONGTEXT NOT NULL DEFAULT ('')"
                )
            else:
                cursor.execute(
                    f"ALTER TABLE {qn(table)} ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
                )

    _add_int_col("duration_hours")
    _add_text_col("line_note")

    with connection.cursor() as cursor:
        if "duration_hours" in existing:
            if connection.vendor == "postgresql":
                cursor.execute(
                    f"UPDATE {qn(table)} SET {qn('duration_hours')} = 1 "
                    f"WHERE {qn('duration_hours')} IS NULL"
                )
            else:
                cursor.execute(
                    f"UPDATE {qn(table)} SET duration_hours = 1 WHERE duration_hours IS NULL"
                )
        if "line_note" in existing:
            if connection.vendor == "postgresql":
                cursor.execute(
                    f"UPDATE {qn(table)} SET {qn('line_note')} = %s WHERE {qn('line_note')} IS NULL",
                    [""],
                )
            elif connection.vendor == "mysql":
                cursor.execute(
                    f"UPDATE {qn(table)} SET line_note = '' WHERE line_note IS NULL"
                )
            else:
                cursor.execute(
                    f"UPDATE {qn(table)} SET line_note = '' WHERE line_note IS NULL"
                )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0033_order_pickup_location"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="orderitem",
                    name="duration_hours",
                    field=models.PositiveIntegerField(default=1),
                ),
                migrations.AddField(
                    model_name="orderitem",
                    name="line_note",
                    field=models.TextField(blank=True, default=""),
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_orderitem_columns, noop_reverse),
            ],
        ),
    ]
