from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0021_devotional"),
    ]

    operations = [
        migrations.AddField(
            model_name="sermon",
            name="is_kickoff",
            field=models.BooleanField(
                default=False,
                help_text="When enabled, sermon can appear in the Kick-Off list (audio, last 5 days by upload time).",
            ),
        ),
    ]
