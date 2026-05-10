from django.db import models
from django.conf import settings
from cloudinary.models import CloudinaryField
from django_summernote.fields import SummernoteTextField


class Sermon(models.Model):
	SERMON_TYPE_VIDEO = 'video'
	SERMON_TYPE_AUDIO = 'audio'
	SERMON_TYPE_CHOICES = [
		(SERMON_TYPE_VIDEO, 'Video'),
		(SERMON_TYPE_AUDIO, 'Audio'),
	]

	title = models.CharField(max_length=255)
	speaker = models.CharField(max_length=255, blank=True)
	description = models.TextField(blank=True)
	category = models.CharField(max_length=100, blank=True)
	sermon_type = models.CharField(max_length=10, choices=SERMON_TYPE_CHOICES)

	# Video
	youtube_url = models.URLField(blank=True, null=True)

	# Audio

    # Audio - badilisha hapa
	audio_file = CloudinaryField(
        'audio',
        resource_type='video',  # muhimu kwa audio!
        blank=True,
        null=True
    )

    # Thumbnail - badilisha hapa
	thumbnail_image = CloudinaryField(
        'image',
        resource_type='image',
        blank=True,
        null=True
    )

	# # audio_file = CloudinaryField(resource_type='video',blank=True,null=True)
	# audio_file = models.FileField(upload_to='sermons/audio/', blank=True, null=True)

	# # Thumbnail
	# thumbnail_image = models.ImageField(upload_to='sermons/thumbnails/', blank=True, null=True)

	duration = models.CharField(max_length=50, blank=True)
	views_count = models.PositiveIntegerField(default=0)
	featured = models.BooleanField(default=False)
	published = models.BooleanField(default=True)
	# Shown on app “Kick-Off” audio list; API only returns if created within the last 5 days.
	is_kickoff = models.BooleanField(
		default=False,
		help_text="Kick-Off tab (audio only): visible for 5 days from upload (created_at).",
	)
	date = models.DateField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-date', '-created_at']

	def __str__(self) -> str:
		return f"{self.title} ({self.get_sermon_type_display()})"

	def clean(self):
		from django.core.exceptions import ValidationError
		# enforce rules depending on sermon_type
		if self.sermon_type == self.SERMON_TYPE_VIDEO and not self.youtube_url:
			raise ValidationError({'youtube_url': 'YouTube URL is required for video sermons.'})
		if self.sermon_type == self.SERMON_TYPE_AUDIO and not self.audio_file:
			raise ValidationError({'audio_file': 'Audio file is required for audio sermons.'})

	def get_thumbnail_url(self):
		if self.thumbnail_image:
			try:
				return self.thumbnail_image.url
			except Exception:
				return None
		# derive from youtube if possible
		if self.youtube_url and ('youtube.com' in self.youtube_url or 'youtu.be' in self.youtube_url):
			try:
				from urllib.parse import urlparse, parse_qs
				url = self.youtube_url
				if 'youtu.be/' in url:
					vid = url.split('youtu.be/').pop().split('?')[0]
				else:
					parsed = urlparse(url)
					qs = parse_qs(parsed.query)
					vid = qs.get('v', [None])[0] or (parsed.path.split('/')[-1] if parsed.path else None)
				if vid:
					return f'https://img.youtube.com/vi/{vid}/hqdefault.jpg'
			except Exception:
				return None
		return None


class Announcement(models.Model):
	title = models.CharField(max_length=255)
	message = models.TextField()
	image = models.ImageField(upload_to='announcements/', blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return self.title


class News(models.Model):
	title = models.CharField(max_length=255)
	body = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return self.title


class NewsImage(models.Model):
	news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='images')
	image = models.ImageField(upload_to='news_images/')
	uploaded_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"Image for {self.news.title}"


class Timetable(models.Model):
	TYPE_WEEK = 'week'
	TYPE_MONTH = 'month'
	TYPE_YEAR = 'year'
	TYPE_CHOICES = [
		(TYPE_WEEK, 'Week'),
		(TYPE_MONTH, 'Month'),
		(TYPE_YEAR, 'Year'),
	]

	title = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	date = models.DateField()
	start_time = models.TimeField()
	end_time = models.TimeField()
	type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_WEEK)
	location = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['date', 'start_time']

	def __str__(self) -> str:
		return f"{self.title} on {self.date}"


class Book(models.Model):
	FILE_PDF = 'pdf'
	FILE_HTML = 'html'
	FILE_TYPE_CHOICES = [
		(FILE_PDF, 'PDF'),
		(FILE_HTML, 'HTML'),
	]

	title = models.CharField(max_length=255)
	author = models.CharField(max_length=255, blank=True)
	description = models.TextField(blank=True)
	cover_image = models.ImageField(upload_to='books/covers/', blank=True, null=True)
	# Raw delivery URLs use `/raw/upload/` on Cloudinary (correct for PDF/HTML files).
	file = CloudinaryField('file', resource_type='raw')
	file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default=FILE_PDF)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return self.title


class Devotional(models.Model):
	title = models.CharField(max_length=255)
	author = models.CharField(max_length=255, blank=True)
	category = models.CharField(max_length=120, blank=True, db_index=True)
	devotion_date = models.DateField(db_index=True)
	scripture_reference = models.CharField(max_length=255, blank=True)
	scripture_text = models.TextField(blank=True)
	excerpt = models.TextField(
		blank=True,
		help_text='Optional teaser for lists; auto-filled from body when left blank.',
	)
	thumbnail = models.ImageField(upload_to='devotionals/thumbnails/', blank=True, null=True)
	content = SummernoteTextField()
	further_study = SummernoteTextField(blank=True)
	golden_nugget = SummernoteTextField(blank=True)
	prayer = SummernoteTextField(blank=True)
	published = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-devotion_date', '-created_at']
		verbose_name_plural = 'Devotionals'

	def __str__(self) -> str:
		return self.title

	def save(self, *args, **kwargs):
		if not (self.excerpt or '').strip():
			from django.utils.html import strip_tags
			plain = strip_tags(self.content or '').strip()
			self.excerpt = (plain[:400] + ('…' if len(plain) > 400 else '')) if plain else ''
		super().save(*args, **kwargs)


class Crusade(models.Model):
	"""City-wide gospel campaign / crusade (CFAN-style content)."""

	title = models.CharField(max_length=255)
	theme = models.CharField(max_length=500, blank=True)
	description = models.TextField(blank=True)
	banner_image = CloudinaryField(
		'image',
		resource_type='image',
		blank=True,
		null=True,
	)
	city = models.CharField(max_length=120)
	country = models.CharField(max_length=120)
	speaker = models.CharField(max_length=255, blank=True)
	start_date = models.DateField(db_index=True)
	end_date = models.DateField(db_index=True)
	start_time = models.CharField(max_length=20, blank=True, help_text='e.g. 17:00')
	end_time = models.CharField(max_length=20, blank=True)
	livestream_url = models.URLField(blank=True)
	souls_saved = models.PositiveIntegerField(default=0)
	miracles_count = models.PositiveIntegerField(default=0)
	attendance_count = models.PositiveIntegerField(default=0)
	is_live = models.BooleanField(default=False, db_index=True)
	published = models.BooleanField(default=True, db_index=True)
	live_attendance = models.PositiveIntegerField(
		default=0,
		help_text='Shown on live crusade screen',
	)
	prayer_comments = models.PositiveIntegerField(default=0)
	online_nations = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-start_date', '-created_at']

	def __str__(self) -> str:
		return self.title


class CrusadeReport(models.Model):
	crusade = models.ForeignKey(
		Crusade,
		on_delete=models.CASCADE,
		related_name='reports',
	)
	title = models.CharField(max_length=255)
	day_label = models.CharField(max_length=80, blank=True)
	body = models.TextField()
	image = CloudinaryField(
		'image',
		resource_type='image',
		blank=True,
		null=True,
	)
	order = models.PositiveSmallIntegerField(default=0)

	class Meta:
		ordering = ['order', 'id']

	def __str__(self) -> str:
		return f'{self.crusade_id} — {self.title}'


class CrusadeTestimony(models.Model):
	crusade = models.ForeignKey(
		Crusade,
		on_delete=models.CASCADE,
		related_name='testimonies',
	)
	name = models.CharField(max_length=120)
	image = models.URLField(max_length=500, blank=True)
	testimony = models.TextField()
	miracle_type = models.CharField(max_length=80, blank=True)
	order = models.PositiveSmallIntegerField(default=0)

	class Meta:
		ordering = ['order', 'id']
		verbose_name_plural = 'Crusade testimonies'

	def __str__(self) -> str:
		return f'{self.name} ({self.crusade_id})'


class CrusadeGalleryItem(models.Model):
	crusade = models.ForeignKey(
		Crusade,
		on_delete=models.CASCADE,
		related_name='gallery_items',
	)
	image = CloudinaryField(
		'image',
		resource_type='image',
		blank=True,
		null=True,
	)
	is_video = models.BooleanField(default=False)
	video_url = models.URLField(blank=True)
	order = models.PositiveSmallIntegerField(default=0)

	class Meta:
		ordering = ['order', 'id']

	def __str__(self) -> str:
		return f'Gallery {self.pk} ({self.crusade_id})'


class CrusadeVideo(models.Model):
	crusade = models.ForeignKey(
		Crusade,
		on_delete=models.CASCADE,
		related_name='videos',
	)
	title = models.CharField(max_length=255)
	youtube_url = models.URLField(blank=True)
	youtube_id = models.CharField(max_length=32, blank=True)
	order = models.PositiveSmallIntegerField(default=0)

	class Meta:
		ordering = ['order', 'id']

	def __str__(self) -> str:
		return self.title


class GospelImpactStats(models.Model):
	"""Singleton-style counters for the Crusades home “Gospel impact” section."""

	total_souls = models.PositiveIntegerField(default=0)
	total_miracles = models.PositiveIntegerField(default=0)
	total_nations = models.PositiveIntegerField(default=0)
	total_crusades = models.PositiveIntegerField(default=0)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'Gospel impact statistics'
		verbose_name_plural = 'Gospel impact statistics'

	def __str__(self) -> str:
		return 'Gospel impact (singleton)'


class Feedback(models.Model):
	name = models.CharField(max_length=255)
	email = models.EmailField()
	message = models.TextField()
	is_read = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return f"Feedback from {self.name} <{self.email}>"


class Service(models.Model):
	title = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	price = models.DecimalField(max_digits=10, decimal_places=2)
	image = models.ImageField(upload_to='services/images/', blank=True, null=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return self.title


class Representative(models.Model):
	full_name = models.CharField(max_length=255)
	phone_number = models.CharField(max_length=50)
	email = models.EmailField(blank=True, null=True)
	country = models.CharField(max_length=100)
	region = models.CharField(max_length=100)
	district = models.CharField(max_length=100)
	ward = models.CharField(max_length=100)
	street = models.CharField(max_length=255, blank=True)
	latitude = models.DecimalField(max_digits=9, decimal_places=6)
	longitude = models.DecimalField(max_digits=9, decimal_places=6)
	profile_image = models.ImageField(upload_to='representatives/', blank=True, null=True)
	is_active = models.BooleanField(default=True)
	linked_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='representative_profile')
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.full_name} ({self.phone_number})"


class PartnerType(models.Model):
	name = models.CharField(max_length=120, unique=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['name']

	def __str__(self):
		return self.name


class Partnership(models.Model):
	CURRENCY_USD = 'USD'
	CURRENCY_TSH = 'TSH'
	CURRENCY_CHOICES = [
		(CURRENCY_USD, 'USD'),
		(CURRENCY_TSH, 'TSH'),
	]

	GIFT_ONE_TIME = 'ONE_TIME'
	GIFT_RECURRING = 'RECURRING'
	GIFT_TYPE_CHOICES = [
		(GIFT_ONE_TIME, 'One Time'),
		(GIFT_RECURRING, 'Recurring'),
	]

	FREQ_WEEKLY = 'WEEKLY'
	FREQ_EVERY_2_WEEKS = 'EVERY_2_WEEKS'
	FREQ_MONTHLY = 'MONTHLY'
	FREQ_1ST_15TH = 'FIRST_AND_FIFTEENTH'
	FREQUENCY_CHOICES = [
		(FREQ_WEEKLY, 'Every week'),
		(FREQ_EVERY_2_WEEKS, 'Every 2 weeks'),
		(FREQ_MONTHLY, 'Every month'),
		(FREQ_1ST_15TH, '1st & 15th monthly'),
	]

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		related_name='partnerships',
		null=True,
		blank=True,
	)
	partner_type = models.ForeignKey(
		PartnerType,
		on_delete=models.PROTECT,
		related_name='partnerships',
	)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
	gift_type = models.CharField(
		max_length=12,
		choices=GIFT_TYPE_CHOICES,
		default=GIFT_ONE_TIME,
	)
	frequency = models.CharField(
		max_length=30,
		choices=FREQUENCY_CHOICES,
		blank=True,
		null=True,
	)
	start_date = models.DateField(blank=True, null=True)
	fund = models.CharField(max_length=120, blank=True, default='Where Needed Most')
	street = models.CharField(max_length=255, blank=True)
	district = models.CharField(max_length=120, blank=True)
	ward = models.CharField(max_length=120, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.partner_type} - {self.amount} {self.currency}"

	def clean(self):
		from django.core.exceptions import ValidationError
		if self.gift_type == self.GIFT_RECURRING and not self.frequency:
			raise ValidationError({'frequency': 'Frequency is required for recurring giving.'})
		if self.gift_type == self.GIFT_ONE_TIME:
			self.frequency = None


class Order(models.Model):
	STATUS_PENDING = 'PENDING'
	STATUS_PROCESSING = 'PROCESSING'
	STATUS_PAID = 'PAID'
	STATUS_FAILED = 'FAILED'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_PROCESSING, 'Processing'),
		(STATUS_PAID, 'Paid'),
		(STATUS_FAILED, 'Failed'),
	]

	PAYMENT_MOBILE = 'MOBILE_MONEY'
	PAYMENT_CARD = 'CARD'
	PAYMENT_METHOD_CHOICES = [
		(PAYMENT_MOBILE, 'Mobile Money'),
		(PAYMENT_CARD, 'Card'),
	]

	user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='orders')
	total_amount = models.DecimalField(max_digits=12, decimal_places=2)
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
	payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
	transaction_id = models.CharField(max_length=255, blank=True, null=True)
	external_reference = models.CharField(max_length=100, blank=True, null=True, unique=True)
	created_at = models.DateTimeField(auto_now_add=True)

	# Optional representative assigned to this order
	representative = models.ForeignKey('Representative', on_delete=models.SET_NULL, related_name='orders', null=True, blank=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return f"Order #{self.id} - {self.user} - {self.status}"


class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
	service = models.ForeignKey(Service, on_delete=models.PROTECT)
	quantity = models.PositiveIntegerField(default=1)
	price = models.DecimalField(max_digits=10, decimal_places=2)

	def __str__(self) -> str:
		return f"{self.quantity} x {self.service.title}"


from django.db.models.signals import post_save
from django.dispatch import receiver

class Payment(models.Model):

    PROVIDER_AZAMPAY = 'AZAMPAY'

    PROVIDER_CHOICES = [
        (PROVIDER_AZAMPAY, 'AzamPay'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        default=PROVIDER_AZAMPAY
    )

    # YOUR INTERNAL REFERENCE
    external_reference = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
		null=True,
		blank=True
    )

    # AZAMPAY TRANSACTION ID
    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    raw_response = models.JSONField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} for Order {self.order_id} - {self.status}"


# class Payment(models.Model):
# 	PROVIDER_AZAMPAY = 'AZAMPAY'
# 	PROVIDER_CHOICES = [
# 		(PROVIDER_AZAMPAY, 'AzamPay'),
# 	]

# 	STATUS_PENDING = 'PENDING'
# 	STATUS_SUCCESS = 'SUCCESS'
# 	STATUS_FAILED = 'FAILED'
# 	STATUS_CHOICES = [
# 		(STATUS_PENDING, 'Pending'),
# 		(STATUS_SUCCESS, 'Success'),
# 		(STATUS_FAILED, 'Failed'),
# 	]

# 	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
# 	amount = models.DecimalField(max_digits=12, decimal_places=2)
# 	provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default=PROVIDER_AZAMPAY)
# 	transaction_id = models.CharField(max_length=255, blank=True, null=True)
# 	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
# 	raw_response = models.JSONField(blank=True, null=True)
# 	created_at = models.DateTimeField(auto_now_add=True)

# 	class Meta:
# 		ordering = ['-created_at']

# 	def __str__(self):
# 		return f"Payment {self.id} for Order {self.order_id} - {self.status}"


class Profile(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
	avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
	gender = models.CharField(max_length=20, blank=True)
	age_group = models.CharField(max_length=50, blank=True)
	phone = models.CharField(max_length=30, blank=True)
	city = models.CharField(max_length=255, blank=True)
	share_profile_data = models.BooleanField(default=False)
	# optional role for convenience (not authoritative, use user.is_staff/is_superuser for permissions)
	ROLE_USER = 'user'
	ROLE_ADMIN = 'admin'
	ROLE_CHOICES = [
		(ROLE_USER, 'User'),
		(ROLE_ADMIN, 'Admin'),
	]
	role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER, blank=True)

	def __str__(self):
		return f"Profile for {self.user.username}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
	if created:
		Profile.objects.create(user=instance)
