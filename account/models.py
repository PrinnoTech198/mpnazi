from django.db import models
from django.conf import settings



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
	audio_file = models.FileField(upload_to='sermons/audio/', blank=True, null=True)

	# Thumbnail
	thumbnail_image = models.ImageField(upload_to='sermons/thumbnails/', blank=True, null=True)

	duration = models.CharField(max_length=50, blank=True)
	views_count = models.PositiveIntegerField(default=0)
	featured = models.BooleanField(default=False)
	published = models.BooleanField(default=True)
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
	file = models.FileField(upload_to='books/files/')
	file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default=FILE_PDF)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return self.title


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
