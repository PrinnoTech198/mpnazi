from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0034_orderitem_duration_line_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="pickup_country",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
    ]
