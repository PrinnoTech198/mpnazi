from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers
from .models import Sermon
from urllib.parse import urlparse, parse_qs


class SermonSerializer(serializers.ModelSerializer):
    youtube_video_id = serializers.SerializerMethodField()
    thumbnail_image = serializers.SerializerMethodField()
    audio_file = serializers.SerializerMethodField()

    class Meta:
        model = Sermon
        fields = [
            'id', 'title', 'speaker', 'description', 'category', 'sermon_type',
            'youtube_url', 'youtube_video_id', 'audio_file', 'thumbnail_image',
            'duration', 'views_count', 'featured', 'published', 'is_kickoff',
            'date', 'created_at'
        ]

    def get_youtube_video_id(self, obj):
        url = obj.youtube_url
        if not url:
            return None
        try:
            if 'youtu.be/' in url:
                return url.split('youtu.be/').pop().split('?').pop(0)
            parsed = urlparse(url)
            if parsed.hostname and 'youtube' in parsed.hostname:
                qs = parse_qs(parsed.query)
                if 'v' in qs:
                    return qs['v'][0]
                # fallback to last path segment
                parts = parsed.path.split('/')
                if parts:
                    return parts[-1]
        except Exception:
            return None
        return None

    def _absolute_url(self, request, path):
        if not path:
            return None
        try:
            return request.build_absolute_uri(path)
        except Exception:
            return path

    def get_thumbnail_image(self, obj):
        request = self.context.get('request')
        if obj.thumbnail_image:
            return self._absolute_url(request, obj.thumbnail_image.url)
        # derive from youtube
        thumb = obj.get_thumbnail_url() if hasattr(obj, 'get_thumbnail_url') else None
        if thumb:
            return thumb
        return None

    def get_audio_file(self, obj):
        request = self.context.get('request')
        if obj.audio_file:
            return self._absolute_url(request, obj.audio_file.url)
        return None


from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'message', 'image', 'created_at', 'is_active']


from .models import News, NewsImage


class NewsImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsImage
        fields = ['id', 'image']


class NewsSerializer(serializers.ModelSerializer):
    images = NewsImageSerializer(many=True, read_only=True)

    class Meta:
        model = News
        fields = ['id', 'title', 'body', 'created_at', 'images']


from .models import Timetable


class TimetableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Timetable
        fields = [
            'id',
            'title',
            'description',
            'date',
            'start_time',
            'end_time',
            'type',
            'location',
            'created_at',
        ]


from .models import Book


class BookSerializer(serializers.ModelSerializer):
    cover_image = serializers.ImageField(read_only=True)
    file = serializers.SerializerMethodField(read_only=True)

    def get_file(self, obj):
        if not getattr(obj, "file", None):
            return ""
        try:
            obj.file.url
            return obj.file.url.replace("/upload/", "/upload/fl_attachment/")
        except Exception:
            return str(obj.file)

    class Meta:
        model = Book
        fields = [
            'id',
            'title',
            'author',
            'description',
            'cover_image',
            'file',
            'file_type',
            'is_active',
            'created_at',
        ]


from .models import Feedback


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'name', 'email', 'message', 'is_read', 'created_at']


from .models import Service, Order, OrderItem


class ServiceSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Service
        fields = ['id', 'title', 'description', 'price', 'image', 'is_active', 'created_at']


class OrderItemSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'service', 'quantity', 'price', 'duration_hours', 'line_note']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    representative = serializers.SerializerMethodField()
    class Meta:
        model = Order
        fields = [
            'id',
            'user',
            'total_amount',
            'status',
            'created_at',
            'customer_note',
            'fulfillment_status',
            'pickup_country',
            'pickup_region',
            'pickup_district',
            'pickup_ward',
            'pickup_village',
            'pickup_landmark',
            'items',
            'representative',
        ]

    def get_representative(self, obj):
        rep = getattr(obj, 'representative', None)
        if not rep:
            return None
        from .serializers import RepresentativeSerializer
        return RepresentativeSerializer(rep, context=self.context).data


from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)
    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'avatar',
            'gender',
            'age_group',
            'phone',
            'city',
            'share_profile_data',
            'role',
            'email_verified_at',
            'email_verified',
        ]

    def get_email_verified(self, obj):
        return obj.email_verified_at is not None


from .models import Representative


class RepresentativeSerializer(serializers.ModelSerializer):
    distance = serializers.FloatField(required=False, read_only=True)

    class Meta:
        model = Representative
        fields = ['id', 'full_name', 'phone_number', 'email', 'country', 'region', 'district', 'ward', 'street', 'latitude', 'longitude', 'profile_image', 'is_active', 'created_at', 'distance']


from .models import PartnerType, Partnership


class PartnerTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerType
        fields = ['id', 'name', 'is_active', 'created_at']


class PartnershipSerializer(serializers.ModelSerializer):
    partner_type_name = serializers.CharField(source='partner_type.name', read_only=True)
    guest_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        write_only=False,
        max_length=254,
    )

    class Meta:
        model = Partnership
        fields = [
            'id',
            'user',
            'partner_type',
            'partner_type_name',
            'guest_email',
            'amount',
            'currency',
            'gift_type',
            'frequency',
            'start_date',
            'fund',
            'street',
            'district',
            'ward',
            'paid_at',
            'created_at',
        ]
        read_only_fields = ['user', 'created_at', 'partner_type_name', 'paid_at']

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if user and user.is_authenticated:
            attrs.pop('guest_email', None)
        else:
            raw = (attrs.get('guest_email') or '').strip()
            if not raw:
                init = getattr(self, 'initial_data', None)
                if init is not None and hasattr(init, 'get'):
                    ge = init.get('guest_email')
                    if ge in (None, '', []):
                        ge = init.get('guestEmail')
                    if isinstance(ge, (list, tuple)) and ge:
                        ge = ge[0]
                    raw = str(ge or '').strip()
            if not raw and self.instance:
                raw = (self.instance.guest_email or '').strip()
            if not raw:
                raise serializers.ValidationError(
                    {'guest_email': 'A valid email address is required for guest partner giving.'}
                )
            try:
                validate_email(raw)
            except DjangoValidationError:
                raise serializers.ValidationError(
                    {'guest_email': 'Please enter a valid email address.'}
                )
            attrs['guest_email'] = raw.lower()

        gift_type = attrs.get('gift_type') or getattr(self.instance, 'gift_type', None)
        frequency = attrs.get('frequency') or getattr(self.instance, 'frequency', None)
        if gift_type == Partnership.GIFT_RECURRING and not frequency:
            raise serializers.ValidationError({'frequency': 'Frequency is required for recurring giving.'})
        if gift_type == Partnership.GIFT_ONE_TIME:
            attrs['frequency'] = None
        return attrs


from .models import Devotional


class DevotionalListSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Devotional
        fields = [
            'id',
            'title',
            'author',
            'category',
            'devotion_date',
            'scripture_reference',
            'scripture_text',
            'excerpt',
            'thumbnail',
        ]

    def _thumbnail_url(self, obj):
        if not obj.thumbnail:
            return None
        try:
            return obj.thumbnail.url
        except Exception:
            return None

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        raw = self._thumbnail_url(obj)
        if not raw:
            return None
        try:
            if request:
                return request.build_absolute_uri(raw)
        except Exception:
            pass
        return raw


class DevotionalDetailSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Devotional
        fields = [
            'id',
            'title',
            'author',
            'category',
            'devotion_date',
            'scripture_reference',
            'scripture_text',
            'excerpt',
            'thumbnail',
            'content',
            'further_study',
            'golden_nugget',
            'prayer',
            'created_at',
        ]

    def get_thumbnail(self, obj):
        return DevotionalListSerializer(context=self.context).get_thumbnail(obj)
