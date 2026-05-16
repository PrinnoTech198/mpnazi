# Safe state migration from Crusade models to unified Event models.
#
# The model names and Python field names change, but the existing database
# tables and FK column names are intentionally preserved:
# - account_crusade remains the event table
# - related tables keep their account_crusade* names
# - related FK columns remain crusade_id
#
# This keeps production data intact and preserves legacy APIs while the app
# moves toward /events/.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0024_crusades_models"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel("Crusade", "Event"),
                migrations.RenameModel("CrusadeReport", "EventReport"),
                migrations.RenameModel("CrusadeTestimony", "EventTestimony"),
                migrations.RenameModel("CrusadeGalleryItem", "EventGalleryItem"),
                migrations.RenameModel("CrusadeVideo", "EventVideo"),
                migrations.AlterModelTable("Event", "account_crusade"),
                migrations.AlterModelTable("EventReport", "account_crusadereport"),
                migrations.AlterModelTable("EventTestimony", "account_crusadetestimony"),
                migrations.AlterModelTable(
                    "EventGalleryItem",
                    "account_crusadegalleryitem",
                ),
                migrations.AlterModelTable("EventVideo", "account_crusadevideo"),
                migrations.RenameField("EventReport", "crusade", "event"),
                migrations.RenameField("EventTestimony", "crusade", "event"),
                migrations.RenameField("EventGalleryItem", "crusade", "event"),
                migrations.RenameField("EventVideo", "crusade", "event"),
                migrations.AlterField(
                    model_name="eventreport",
                    name="event",
                    field=models.ForeignKey(
                        db_column="crusade_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="account.event",
                    ),
                ),
                migrations.AlterField(
                    model_name="eventtestimony",
                    name="event",
                    field=models.ForeignKey(
                        db_column="crusade_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="testimonies",
                        to="account.event",
                    ),
                ),
                migrations.AlterField(
                    model_name="eventgalleryitem",
                    name="event",
                    field=models.ForeignKey(
                        db_column="crusade_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gallery_items",
                        to="account.event",
                    ),
                ),
                migrations.AlterField(
                    model_name="eventvideo",
                    name="event",
                    field=models.ForeignKey(
                        db_column="crusade_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="videos",
                        to="account.event",
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.AddField(
            model_name="event",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("crusade", "Crusade"),
                    ("seminar", "Seminar"),
                    ("conference", "Conference"),
                    ("revival", "Revival"),
                    ("kongamano", "Kongamano"),
                    ("mkutano", "Mkutano"),
                ],
                db_index=True,
                default="crusade",
                max_length=24,
            ),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["event_type", "published", "is_live"],
                name="acct_event_type_pub_live_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["event_type", "start_date"],
                name="acct_event_type_start_idx",
            ),
        ),
    ]
