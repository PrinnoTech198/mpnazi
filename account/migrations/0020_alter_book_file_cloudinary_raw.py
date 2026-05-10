# Generated manually: Book.file stores PDF/HTML on Cloudinary as resource_type raw.

import cloudinary.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0019_partnertype_partnership"),
    ]

    operations = [
        migrations.AlterField(
            model_name="book",
            name="file",
            field=cloudinary.models.CloudinaryField(
                max_length=255,
                resource_type="raw",
                verbose_name="file",
            ),
        ),
    ]
