from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_version", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="appversioncontrol",
            name="unique_active_app_version_control",
        ),
        migrations.AlterField(
            model_name="appversioncontrol",
            name="playstore_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="Google Play Store listing URL.",
                max_length=512,
            ),
        ),
    ]
