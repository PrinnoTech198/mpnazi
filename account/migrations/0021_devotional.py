# Generated manually — run `manage.py migrate` when Python is available.

from django.db import migrations, models
import django_summernote.fields


class Migration(migrations.Migration):

	dependencies = [
		('account', '0020_alter_book_file_cloudinary_raw'),
	]

	operations = [
		migrations.CreateModel(
			name='Devotional',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('title', models.CharField(max_length=255)),
				('author', models.CharField(blank=True, max_length=255)),
				('category', models.CharField(blank=True, db_index=True, max_length=120)),
				('devotion_date', models.DateField(db_index=True)),
				('scripture_reference', models.CharField(blank=True, max_length=255)),
				('scripture_text', models.TextField(blank=True)),
				('excerpt', models.TextField(blank=True, help_text='Optional teaser for lists; auto-filled from body when left blank.')),
				('thumbnail', models.ImageField(blank=True, null=True, upload_to='devotionals/thumbnails/')),
				('content', django_summernote.fields.SummernoteTextField()),
				('further_study', django_summernote.fields.SummernoteTextField(blank=True)),
				('golden_nugget', django_summernote.fields.SummernoteTextField(blank=True)),
				('prayer', django_summernote.fields.SummernoteTextField(blank=True)),
				('published', models.BooleanField(default=True)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('updated_at', models.DateTimeField(auto_now=True)),
			],
			options={
				'verbose_name_plural': 'Devotionals',
				'ordering': ['-devotion_date', '-created_at'],
			},
		),
	]
