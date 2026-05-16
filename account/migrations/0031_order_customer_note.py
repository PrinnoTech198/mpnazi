# customer_note may already exist on account_order (NOT NULL) outside repo migrations;
# keep DB and Django state aligned without duplicate ADD COLUMN errors.

from django.db import migrations, models


def add_customer_note_if_needed(apps, schema_editor):
    Order = apps.get_model("account", "Order")
    table = Order._meta.db_table
    connection = schema_editor.connection
    qn = connection.ops.quote_name

    with connection.cursor() as cursor:
        try:
            cols = [c.name for c in connection.introspection.get_table_description(cursor, table)]
        except Exception:
            return
        if "customer_note" in cols:
            return

    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN {qn('customer_note')} TEXT NOT NULL DEFAULT %s",
                [""],
            )
            cursor.execute(
                f"ALTER TABLE {qn(table)} ALTER COLUMN {qn('customer_note')} DROP DEFAULT"
            )
        elif connection.vendor == "sqlite":
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN customer_note TEXT NOT NULL DEFAULT ''"
            )
        elif connection.vendor == "mysql":
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN customer_note LONGTEXT NOT NULL DEFAULT ('')"
            )
        else:
            cursor.execute(
                f"ALTER TABLE {qn(table)} ADD COLUMN customer_note TEXT NOT NULL DEFAULT ''"
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0030_email_otp_challenge_profile_verified"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="order",
                    name="customer_note",
                    field=models.TextField(blank=True, default=""),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_customer_note_if_needed, noop_reverse),
            ],
        ),
    ]
