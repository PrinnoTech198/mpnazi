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
            'duration', 'views_count', 'featured', 'published', 'date', 'created_at'
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
    file = serializers.FileField(read_only=True)

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
        fields = ['id', 'service', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    representative = serializers.SerializerMethodField()
    class Meta:
        model = Order
        fields = ['id', 'user', 'total_amount', 'status', 'created_at', 'items', 'representative']

    def get_representative(self, obj):
        rep = getattr(obj, 'representative', None)
        if not rep:
            return None
        from .serializers import RepresentativeSerializer
        return RepresentativeSerializer(rep, context=self.context).data


from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = ['avatar', 'gender', 'age_group', 'phone', 'city', 'share_profile_data', 'role']


from .models import Representative

from .models import Payment, Order


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'amount', 'provider', 'transaction_id', 'status', 'raw_response', 'created_at']


class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'status', 'payment_method', 'transaction_id', 'external_reference']


class RepresentativeSerializer(serializers.ModelSerializer):
    distance = serializers.FloatField(required=False, read_only=True)

    class Meta:
        model = Representative
        fields = ['id', 'full_name', 'phone_number', 'email', 'country', 'region', 'district', 'ward', 'street', 'latitude', 'longitude', 'profile_image', 'is_active', 'created_at', 'distance']
