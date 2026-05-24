from django.contrib import admin
from .models import Sermon


@admin.register(Sermon)
class SermonAdmin(admin.ModelAdmin):
	list_display = ('title', 'speaker', 'sermon_type', 'category', 'is_kickoff', 'featured', 'published', 'date', 'views_count')
	list_filter = ('sermon_type', 'published', 'featured', 'is_kickoff', 'date', 'category')
	search_fields = ('title', 'description', 'speaker')
	readonly_fields = ('created_at', 'views_count')
	fieldsets = (
		(None, {'fields': ('title', 'speaker', 'description', 'category', 'sermon_type', 'is_kickoff', 'featured', 'published', 'date')}),
		('Media', {'fields': ('youtube_url', 'audio_file', 'thumbnail_image', 'duration')}),
		('Meta', {'fields': ('views_count', 'created_at')}),
	)

	def thumbnail_preview(self, obj):
		url = obj.get_thumbnail_url() if hasattr(obj, 'get_thumbnail_url') else None
		if url:
			from django.utils.safestring import mark_safe
			return mark_safe(f'<img src="{url}" style="max-height: 100px;"/>')
		return ''
	thumbnail_preview.short_description = 'Thumbnail'


from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
	list_display = ('title', 'is_active', 'created_at')
	list_filter = ('is_active', 'created_at')
	search_fields = ('title', 'message')
	readonly_fields = ('created_at',)


from .models import News, NewsImage


class NewsImageInline(admin.TabularInline):
	model = NewsImage
	extra = 1


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
	list_display = ('title', 'created_at')
	inlines = [NewsImageInline]
	search_fields = ('title', 'body')


from .models import Timetable


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
	list_display = ('title', 'date', 'start_time', 'end_time', 'type', 'location')
	list_filter = ('type', 'date')
	search_fields = ('title', 'description', 'location')
	readonly_fields = ('created_at',)


from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
	list_display = ('title', 'author', 'is_active', 'created_at')
	list_filter = ('is_active', 'created_at')
	search_fields = ('title', 'author')
	readonly_fields = ('created_at',)
	fieldsets = (
		(None, {
			'fields': ('title', 'author', 'description')
		}),
		('Files', {
			'fields': ('cover_image', 'file', 'file_type', 'is_active')
		}),
	)


from django_summernote.admin import SummernoteModelAdmin
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import Devotional


@admin.register(Devotional)
class DevotionalAdmin(SummernoteModelAdmin):
	list_display = ('title', 'author', 'category', 'devotion_date', 'published', 'created_at')
	list_filter = ('published', 'category', 'devotion_date')
	search_fields = ('title', 'author', 'scripture_reference', 'category')
	readonly_fields = ('created_at', 'updated_at')
	fieldsets = (
		(None, {
			'fields': ('title', 'author', 'category', 'devotion_date', 'published', 'thumbnail')
		}),
		('Scripture', {
			'fields': ('scripture_reference', 'scripture_text', 'excerpt')
		}),
		('Body', {
			'fields': ('content', 'further_study', 'golden_nugget', 'prayer')
		}),
		('Meta', {
			'fields': ('created_at', 'updated_at')
		}),
	)

	def save_model(self, request, obj, form, change):
		try:
			super().save_model(request, obj, form, change)
		except (ValueError, ValidationError) as exc:
			msg = str(exc)
			if "api_key" in msg.lower() or "cloudinary" in msg.lower():
				messages.error(
					request,
					"Could not upload media: Cloudinary is not configured on the server. "
					"Add CLOUD_NAME, API_KEY, and API_SECRET to Railway environment variables, "
					"or save without a thumbnail.",
				)
			raise


from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
	list_display = ('name', 'email', 'is_read', 'created_at')
	list_filter = ('is_read', 'created_at')
	search_fields = ('name', 'email', 'message')
	readonly_fields = ('created_at',)
	actions = ['mark_as_read']

	def mark_as_read(self, request, queryset):
		queryset.update(is_read=True)
	mark_as_read.short_description = 'Mark selected feedback as read'


from .models import Service, Order, OrderItem


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
	list_display = ('title', 'price', 'is_active', 'created_at')
	list_filter = ('is_active', 'created_at')
	search_fields = ('title', 'description')


class OrderItemInline(admin.TabularInline):
	model = OrderItem
	extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'total_amount', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	inlines = [OrderItemInline]
	readonly_fields = ('created_at',)


from .models import EmailOTPChallenge, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'user_email', 'phone', 'city', 'email_verified_at', 'share_profile_data')
	search_fields = ('user__username', 'user__email', 'phone', 'city')
	readonly_fields = ('email_verified_at',)

	@admin.display(description='Email', ordering='user__email')
	def user_email(self, obj):
		return obj.user.email if obj.user_id else ''


@admin.register(EmailOTPChallenge)
class EmailOTPChallengeAdmin(admin.ModelAdmin):
	"""Staff CRUD for email OTP challenges (registration + password reset)."""

	list_display = (
		'id',
		'email',
		'verification_code',
		'status_code',
		'purpose',
		'user',
		'failed_attempts',
		'expires_at',
		'used_at',
		'created_at',
	)
	list_filter = ('status_code', 'purpose', 'created_at')
	search_fields = ('email', 'verification_code', 'user__email', 'user__username')
	readonly_fields = ('code_hash', 'created_at')
	ordering = ('-created_at',)
	raw_id_fields = ('user',)
	fieldsets = (
		(None, {
			'fields': (
				'email',
				'verification_code',
				'status_code',
				'purpose',
				'user',
			),
		}),
		('Validity', {
			'fields': ('expires_at', 'used_at', 'failed_attempts'),
		}),
		('Internal', {
			'fields': ('code_hash', 'created_at'),
			'classes': ('collapse',),
		}),
	)


from .models import Representative


@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
	list_display = ('full_name', 'phone_number', 'country', 'region', 'district', 'ward', 'is_active', 'created_at')
	list_filter = ('is_active', 'country', 'region')
	search_fields = ('full_name', 'phone_number', 'email')
	readonly_fields = ('created_at',)


from .models import PartnerType, Partnership, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = (
		'id', 'order', 'partnership', 'amount', 'provider', 'status',
		'external_reference', 'provider_transaction_id', 'utility_reference', 'created_at',
	)
	list_filter = ('provider', 'status', 'created_at')
	readonly_fields = ('raw_response', 'created_at')
	search_fields = ('external_reference', 'provider_transaction_id', 'utility_reference')


@admin.register(PartnerType)
class PartnerTypeAdmin(admin.ModelAdmin):
	list_display = ('name', 'is_active', 'created_at')
	list_filter = ('is_active',)
	search_fields = ('name',)


@admin.register(Partnership)
class PartnershipAdmin(admin.ModelAdmin):
	list_display = (
		'id', 'user', 'partner_type', 'amount', 'currency', 'gift_type', 'frequency',
		'next_reminder_at', 'paid_at', 'district', 'ward', 'created_at',
	)
	list_filter = ('currency', 'gift_type', 'frequency', 'partner_type')
	search_fields = ('user__username', 'street', 'district', 'ward', 'fund')


from .models import (
	Event,
	EventGalleryItem,
	EventReport,
	EventTestimony,
	EventVideo,
	GospelImpactStats,
)


class EventReportInline(admin.TabularInline):
	model = EventReport
	extra = 0
	ordering = ('order', 'id')


class EventTestimonyInline(admin.TabularInline):
	model = EventTestimony
	extra = 0
	ordering = ('order', 'id')


class EventGalleryItemInline(admin.TabularInline):
	model = EventGalleryItem
	extra = 0
	ordering = ('order', 'id')


class EventVideoInline(admin.TabularInline):
	model = EventVideo
	extra = 0
	ordering = ('order', 'id')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
	list_display = (
		'title',
		'event_type',
		'city',
		'country',
		'start_date',
		'end_date',
		'is_live',
		'published',
		'created_at',
	)
	list_filter = ('event_type', 'is_live', 'published', 'country', 'start_date')
	search_fields = ('title', 'theme', 'description', 'city', 'speaker')
	readonly_fields = ('created_at', 'updated_at')
	inlines = [
		EventReportInline,
		EventTestimonyInline,
		EventGalleryItemInline,
		EventVideoInline,
	]
	fieldsets = (
		(None, {'fields': ('title', 'event_type', 'theme', 'description', 'speaker', 'published', 'is_live')}),
		('Location & dates', {'fields': ('city', 'country', 'start_date', 'end_date', 'start_time', 'end_time')}),
		('Media', {'fields': ('banner_image', 'livestream_url')}),
		('Stats', {'fields': ('souls_saved', 'miracles_count', 'attendance_count')}),
		('Live UI metrics', {'fields': ('live_attendance', 'prayer_comments', 'online_nations')}),
		('Meta', {'fields': ('created_at', 'updated_at')}),
	)


@admin.register(GospelImpactStats)
class GospelImpactStatsAdmin(admin.ModelAdmin):
	list_display = ('total_souls', 'total_miracles', 'total_nations', 'total_crusades', 'updated_at')
	readonly_fields = ('updated_at',)

	def has_add_permission(self, request):
		return not GospelImpactStats.objects.exists()

	def has_delete_permission(self, request, obj=None):
		return False
