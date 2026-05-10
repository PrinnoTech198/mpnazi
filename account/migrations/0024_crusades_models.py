# Generated manually for Crusades feature

import cloudinary.models
from django.db import migrations, models
import django.db.models.deletion


def seed_gospel_impact_row(apps, schema_editor):
    GospelImpactStats = apps.get_model("account", "GospelImpactStats")
    if not GospelImpactStats.objects.filter(pk=1).exists():
        GospelImpactStats.objects.create(
            pk=1,
            total_souls=0,
            total_miracles=0,
            total_nations=0,
            total_crusades=0,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0023_alter_sermon_is_kickoff"),
    ]

    operations = [
        migrations.CreateModel(
            name="Crusade",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("theme", models.CharField(blank=True, max_length=500)),
                ("description", models.TextField(blank=True)),
                (
                    "banner_image",
                    cloudinary.models.CloudinaryField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="image",
                    ),
                ),
                ("city", models.CharField(max_length=120)),
                ("country", models.CharField(max_length=120)),
                ("speaker", models.CharField(blank=True, max_length=255)),
                ("start_date", models.DateField(db_index=True)),
                ("end_date", models.DateField(db_index=True)),
                (
                    "start_time",
                    models.CharField(
                        blank=True,
                        help_text="e.g. 17:00",
                        max_length=20,
                    ),
                ),
                ("end_time", models.CharField(blank=True, max_length=20)),
                ("livestream_url", models.URLField(blank=True)),
                ("souls_saved", models.PositiveIntegerField(default=0)),
                ("miracles_count", models.PositiveIntegerField(default=0)),
                ("attendance_count", models.PositiveIntegerField(default=0)),
                ("is_live", models.BooleanField(db_index=True, default=False)),
                ("published", models.BooleanField(db_index=True, default=True)),
                (
                    "live_attendance",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Shown on live crusade screen",
                    ),
                ),
                ("prayer_comments", models.PositiveIntegerField(default=0)),
                ("online_nations", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-start_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="GospelImpactStats",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("total_souls", models.PositiveIntegerField(default=0)),
                ("total_miracles", models.PositiveIntegerField(default=0)),
                ("total_nations", models.PositiveIntegerField(default=0)),
                ("total_crusades", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Gospel impact statistics",
                "verbose_name_plural": "Gospel impact statistics",
            },
        ),
        migrations.CreateModel(
            name="CrusadeReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("day_label", models.CharField(blank=True, max_length=80)),
                ("body", models.TextField()),
                (
                    "image",
                    cloudinary.models.CloudinaryField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="image",
                    ),
                ),
                ("order", models.PositiveSmallIntegerField(default=0)),
                (
                    "crusade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="account.crusade",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="CrusadeTestimony",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("image", models.URLField(blank=True, max_length=500)),
                ("testimony", models.TextField()),
                ("miracle_type", models.CharField(blank=True, max_length=80)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                (
                    "crusade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="testimonies",
                        to="account.crusade",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
                "verbose_name_plural": "Crusade testimonies",
            },
        ),
        migrations.CreateModel(
            name="CrusadeGalleryItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    cloudinary.models.CloudinaryField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="image",
                    ),
                ),
                ("is_video", models.BooleanField(default=False)),
                ("video_url", models.URLField(blank=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                (
                    "crusade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gallery_items",
                        to="account.crusade",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="CrusadeVideo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("youtube_url", models.URLField(blank=True)),
                ("youtube_id", models.CharField(blank=True, max_length=32)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                (
                    "crusade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="videos",
                        to="account.crusade",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed_gospel_impact_row, noop_reverse),
    ]
