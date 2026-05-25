# Restore Summernote fields (revert CKEditor5; DB columns stay TextField).

import django_summernote.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0044_devotional_ckeditor5"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devotional",
            name="content",
            field=django_summernote.fields.SummernoteTextField(),
        ),
        migrations.AlterField(
            model_name="devotional",
            name="further_study",
            field=django_summernote.fields.SummernoteTextField(blank=True),
        ),
        migrations.AlterField(
            model_name="devotional",
            name="golden_nugget",
            field=django_summernote.fields.SummernoteTextField(blank=True),
        ),
        migrations.AlterField(
            model_name="devotional",
            name="prayer",
            field=django_summernote.fields.SummernoteTextField(blank=True),
        ),
    ]
