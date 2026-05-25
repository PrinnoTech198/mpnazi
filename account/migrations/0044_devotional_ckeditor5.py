# Swap Summernote fields for django-ckeditor-5 (DB columns stay TextField).

import django_ckeditor_5.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0043_alter_devotional_thumbnail"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devotional",
            name="content",
            field=django_ckeditor_5.fields.CKEditor5Field(config_name="devotional"),
        ),
        migrations.AlterField(
            model_name="devotional",
            name="further_study",
            field=django_ckeditor_5.fields.CKEditor5Field(
                blank=True, config_name="devotional"
            ),
        ),
        migrations.AlterField(
            model_name="devotional",
            name="golden_nugget",
            field=django_ckeditor_5.fields.CKEditor5Field(
                blank=True, config_name="devotional"
            ),
        ),
        migrations.AlterField(
            model_name="devotional",
            name="prayer",
            field=django_ckeditor_5.fields.CKEditor5Field(
                blank=True, config_name="devotional"
            ),
        ),
    ]
