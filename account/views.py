from rest_framework import viewsets, filters as drf_filters
from mpanzi.http_cache import ListConditionalGetMixin, ConditionalGetMixin
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Sermon
from .serializers import SermonSerializer
from .models import Announcement
from .models import News, NewsImage
from .models import Timetable
from .models import Book
from .models import Feedback
from .models import Service, Order, OrderItem, Representative, PartnerType, Partnership, Devotional
from .models import (
    Event,
    EventGalleryItem,
    EventReport,
    EventTestimony,
    EventType,
    EventVideo,
    GospelImpactStats,
)
from django.db.models import Prefetch
from .crusades_serializers import (
    EventDetailSerializer,
    EventGalleryItemSerializer,
    EventReportSerializer,
    EventSerializer,
    EventTestimonySerializer,
    EventVideoSerializer,
)
from .serializers import AnnouncementSerializer, NewsSerializer, NewsImageSerializer, TimetableSerializer, BookSerializer, FeedbackSerializer, ServiceSerializer, OrderSerializer, OrderItemSerializer, RepresentativeSerializer, PartnerTypeSerializer, PartnershipSerializer, DevotionalListSerializer, DevotionalDetailSerializer

from rest_framework import permissions, parsers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import authentication_classes
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from .models import Profile
from .serializers import ProfileSerializer
from rest_framework import status
from .permissions import PublicReadAdminWrite
from django.utils import timezone as django_timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class SermonViewSet(ListConditionalGetMixin, viewsets.ModelViewSet):
    """Sermons API - list, retrieve for public; CRUD for admin."""
    queryset = Sermon.objects.all()
    serializer_class = SermonSerializer
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    filterset_fields = ['category', 'sermon_type', 'featured', 'published', 'is_kickoff']
    search_fields = ['title', 'description', 'speaker']
    ordering_fields = ['date', 'views_count', 'created_at']
    ordering = ['-date']
    pagination_class = StandardResultsSetPagination

    permission_classes = [PublicReadAdminWrite]

    def get_queryset(self):
        qs = super().get_queryset()
        # only published for anonymous users
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(published=True)
        # filter by sermon_type query param for backward compatibility
        st = self.request.query_params.get('sermon_type') or self.request.query_params.get('type')
        if st in (Sermon.SERMON_TYPE_AUDIO, Sermon.SERMON_TYPE_VIDEO):
            qs = qs.filter(sermon_type=st)
        kickoff = self.request.query_params.get('is_kickoff')
        if kickoff is not None and str(kickoff).lower() in ('1', 'true', 'yes'):
            cutoff = django_timezone.now() - timedelta(days=5)
            qs = qs.filter(is_kickoff=True, created_at__gte=cutoff)
        return qs

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # increment views
        try:
            instance.views_count = (instance.views_count or 0) + 1
            instance.save(update_fields=['views_count'])
        except Exception:
            pass
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        qs = self.get_queryset().filter(featured=True)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class AnnouncementViewSet(ListConditionalGetMixin, viewsets.ModelViewSet):
    """Admin can create/update/delete. Public can read/list active announcements."""
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    permission_classes = [PublicReadAdminWrite]

    def get_queryset(self):
        qs = super().get_queryset()
        # For anonymous/public (non-admin) users, only return active ones
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs.order_by('-created_at')


class NewsViewSet(ConditionalGetMixin, viewsets.ModelViewSet):
    queryset = News.objects.all()
    serializer_class = NewsSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    permission_classes = [PublicReadAdminWrite]

    def create(self, request, *args, **kwargs):
        # Expect title, body in request.data and files in request.FILES.getlist('images')
        title = request.data.get('title')
        body = request.data.get('body')
        if not title or not body:
            return Response({'detail': 'title and body are required'}, status=400)

        news = News.objects.create(title=title, body=body)
        images = request.FILES.getlist('images')
        for img in images:
            NewsImage.objects.create(news=news, image=img)

        serializer = self.get_serializer(news)
        return Response(serializer.data, status=201)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.title = request.data.get('title', instance.title)
        instance.body = request.data.get('body', instance.body)
        instance.save()
        # Handle additional images (append)
        images = request.FILES.getlist('images')
        for img in images:
            NewsImage.objects.create(news=instance, image=img)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class TimetableViewSet(viewsets.ModelViewSet):
    """Timetable CRUD and listing. Admin-only for unsafe methods."""
    queryset = Timetable.objects.all()
    serializer_class = TimetableSerializer

    permission_classes = [PublicReadAdminWrite]

    def get_queryset(self):
        qs = super().get_queryset()
        # filter by type query param: ?type=week|month|year
        t = self.request.query_params.get('type')
        if t in (Timetable.TYPE_WEEK, Timetable.TYPE_MONTH, Timetable.TYPE_YEAR):
            qs = qs.filter(type=t)

        # optional date range: ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        start = self.request.query_params.get('start_date')
        end = self.request.query_params.get('end_date')
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)

        # upcoming only: ?upcoming=true -> date >= today
        upcoming = self.request.query_params.get('upcoming')
        if upcoming and upcoming.lower() in ('1', 'true', 'yes'):
            from django.utils import timezone
            today = timezone.localdate()
            qs = qs.filter(date__gte=today)

        return qs.order_by('date', 'start_time')


class BookViewSet(ListConditionalGetMixin, viewsets.ModelViewSet):
    """Books listing and admin CRUD."""
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    permission_classes = [PublicReadAdminWrite]

    def get_queryset(self):
        qs = super().get_queryset()
        # Only return active books for non-admin users
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs.order_by('-created_at')


class DevotionalViewSet(ListConditionalGetMixin, viewsets.ModelViewSet):
    """Public list/retrieve; HTML bodies edited in admin via django-ckeditor-5."""

    queryset = Devotional.objects.all()
    pagination_class = StandardResultsSetPagination
    filter_backends = [drf_filters.SearchFilter]
    search_fields = ('title', 'author', 'category', 'scripture_reference', 'content')
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    permission_classes = [PublicReadAdminWrite]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DevotionalDetailSerializer
        return DevotionalListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(published=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__iexact=category.strip())
        return qs.order_by('-devotion_date', '-created_at')


class EventViewSet(viewsets.ModelViewSet):
    """Public read; staff CRUD. Nested reports/testimonies/gallery/videos on retrieve."""

    queryset = Event.objects.all()
    permission_classes = [PublicReadAdminWrite]
    pagination_class = StandardResultsSetPagination
    filter_backends = [drf_filters.OrderingFilter]
    ordering_fields = ['start_date', 'created_at', 'id', 'event_type']
    ordering = ['-created_at', '-start_date']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EventDetailSerializer
        return EventSerializer

    def get_queryset(self):
        qs = Event.objects.all()
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(published=True)
        requested_type = (
            self.request.query_params.get('event_type') or ''
        ).strip().lower()
        allowed_types = {choice.value for choice in EventType}
        if requested_type in allowed_types:
            qs = qs.filter(event_type=requested_type)
        elif getattr(self, 'basename', '') == 'crusade':
            qs = qs.filter(event_type=EventType.CRUSADE)
        live = self.request.query_params.get('live')
        if live is not None and str(live).lower() in ('1', 'true', 'yes'):
            qs = qs.filter(is_live=True)
        scope = (self.request.query_params.get('scope') or '').strip().lower()
        if scope:
            today = django_timezone.now().date()
            if scope == 'upcoming':
                qs = qs.filter(start_date__gt=today).exclude(is_live=True)
            elif scope == 'past':
                qs = qs.filter(end_date__lt=today).exclude(is_live=True)
            elif scope == 'live':
                qs = qs.filter(is_live=True)
        if self.action == 'retrieve':
            qs = qs.prefetch_related(
                Prefetch(
                    'reports',
                    queryset=EventReport.objects.order_by('order', 'id'),
                ),
                Prefetch(
                    'testimonies',
                    queryset=EventTestimony.objects.order_by('order', 'id'),
                ),
                Prefetch(
                    'gallery_items',
                    queryset=EventGalleryItem.objects.order_by('order', 'id'),
                ),
                Prefetch(
                    'videos',
                    queryset=EventVideo.objects.order_by('order', 'id'),
                ),
            )
        return qs

    @action(detail=False, methods=['get'])
    def types(self, request):
        """Distinct event_type values that have at least one published event."""
        published_values = set(
            Event.objects.filter(published=True)
            .values_list('event_type', flat=True)
            .distinct()
        )
        payload = [
            {'value': choice.value, 'label': choice.label}
            for choice in EventType
            if choice.value in published_values
        ]
        return Response(payload)

    @action(detail=False, methods=['get'], url_path='gospel-impact')
    def gospel_impact(self, request):
        stats, _ = GospelImpactStats.objects.get_or_create(pk=1)
        return Response(
            {
                'total_souls': stats.total_souls,
                'total_miracles': stats.total_miracles,
                'total_nations': stats.total_nations,
                'total_crusades': stats.total_crusades,
            }
        )

    @action(detail=True, methods=['get'], url_path='reports')
    def reports_list(self, request, pk=None):
        event = self.get_object()
        ser = EventReportSerializer(
            event.reports.all(),
            many=True,
            context={'request': request},
        )
        return Response(ser.data)

    @action(detail=True, methods=['get'], url_path='testimonies')
    def testimonies_list(self, request, pk=None):
        event = self.get_object()
        ser = EventTestimonySerializer(
            event.testimonies.all(),
            many=True,
            context={'request': request},
        )
        return Response(ser.data)

    @action(detail=True, methods=['get'], url_path='gallery')
    def gallery_list(self, request, pk=None):
        event = self.get_object()
        ser = EventGalleryItemSerializer(
            event.gallery_items.all(),
            many=True,
            context={'request': request},
        )
        return Response(ser.data)

    @action(detail=True, methods=['get'], url_path='videos')
    def videos_list(self, request, pk=None):
        event = self.get_object()
        ser = EventVideoSerializer(
            event.videos.all(),
            many=True,
            context={'request': request},
        )
        return Response(ser.data)

    @action(detail=True, methods=['get'], url_path='live-meta')
    def live_meta(self, request, pk=None):
        c = self.get_object()
        return Response(
            {
                'crusade_id': str(c.pk),
                'event_id': str(c.pk),
                'live_attendance': c.live_attendance,
                'prayer_comments': c.prayer_comments,
                'online_nations': c.online_nations,
            }
        )


CrusadeViewSet = EventViewSet


class FeedbackViewSet(viewsets.ModelViewSet):
    """Public create, admin list/update/delete."""
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer

    def get_permissions(self):
        # Allow anyone to create (POST), but restrict list/detail/modify to admin
        if self.request.method == 'POST':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        # optional filter by is_read
        is_read = self.request.query_params.get('is_read')
        if is_read in ('1', 'true', 'True', 'yes'):
            qs = qs.filter(is_read=True)
        elif is_read in ('0', 'false', 'False', 'no'):
            qs = qs.filter(is_read=False)
        return qs.order_by('-created_at')



class ServiceViewSet(ConditionalGetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]


class AdminServiceViewSet(viewsets.ModelViewSet):
    """Admin CRUD for services (explicitly used by admin)."""
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer

    def get_permissions(self):
        return [permissions.IsAdminUser()]


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        # creation allowed for authenticated users, listing only for owner/admin
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        if user and user.is_staff:
            return Order.objects.all().order_by('-created_at')
        if user:
            return Order.objects.filter(user=user).order_by('-created_at')
        return Order.objects.none()

    def create(self, request, *args, **kwargs):
        # Expect items: [{service_id, quantity}]
        user = request.user
        if not user or not user.is_authenticated:
            return Response({'detail': 'Authentication required'}, status=401)

        items = request.data.get('items')
        if not items or not isinstance(items, list):
            return Response({'detail': 'items required'}, status=400)

        linked_rep = Representative.objects.filter(
            linked_user=user, is_active=True
        ).first()

        rep_id = request.data.get("representative_id")

        def _pickup_str(key):
            v = request.data.get(key)
            if v is None:
                return ""
            return str(v).strip()[:255]

        def _pickup_str_req(key):
            v = request.data.get(key)
            if v is None:
                return ""
            return str(v).strip()[:255]

        def _full_pickup_missing(
            pickup_country,
            pickup_region,
            pickup_district,
            pickup_ward,
            pickup_village,
            pickup_landmark,
        ):
            return [
                label
                for label, val in (
                    ("pickup_country", pickup_country),
                    ("pickup_region", pickup_region),
                    ("pickup_district", pickup_district),
                    ("pickup_ward", pickup_ward),
                    ("pickup_village", pickup_village),
                    ("pickup_landmark", pickup_landmark),
                )
                if not val
            ]

        rep = None
        if linked_rep:
            rep = linked_rep
            if rep_id and int(rep_id) != rep.id:
                return Response(
                    {
                        "detail": "Your account is linked to a representative profile; orders are assigned to that profile only."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pickup_country = _pickup_str_req("pickup_country")
            pickup_region = _pickup_str_req("pickup_region")
            pickup_district = _pickup_str_req("pickup_district")
            pickup_ward = _pickup_str_req("pickup_ward")
            pickup_village = _pickup_str_req("pickup_village")
            pickup_landmark = _pickup_str_req("pickup_landmark")
            missing = _full_pickup_missing(
                pickup_country,
                pickup_region,
                pickup_district,
                pickup_ward,
                pickup_village,
                pickup_landmark,
            )
            if missing:
                return Response(
                    {
                        "detail": "Representative accounts must send a full receive location: country, region, district, ward, village, and landmark / popular center.",
                        "missing": missing,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif rep_id:
            try:
                rep = Representative.objects.get(pk=int(rep_id), is_active=True)
            except Exception:
                return Response(
                    {"detail": "Invalid or inactive representative_id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Prefer client payload; fall back to representative location so DB NOT NULL columns stay valid.
            pickup_country = _pickup_str("pickup_country")
            pickup_region = _pickup_str("pickup_region") or (rep.region or "").strip()[:255]
            pickup_district = _pickup_str("pickup_district") or (rep.district or "").strip()[:255]
            pickup_ward = _pickup_str("pickup_ward") or (rep.ward or "").strip()[:255]
            pickup_village = _pickup_str("pickup_village") or (rep.street or "").strip()[:255]
            pickup_landmark = _pickup_str("pickup_landmark") or (rep.street or "").strip()[:255]
        else:
            pickup_country = _pickup_str_req("pickup_country")
            pickup_region = _pickup_str_req("pickup_region")
            pickup_district = _pickup_str_req("pickup_district")
            pickup_ward = _pickup_str_req("pickup_ward")
            pickup_village = _pickup_str_req("pickup_village")
            pickup_landmark = _pickup_str_req("pickup_landmark")
            missing = _full_pickup_missing(
                pickup_country,
                pickup_region,
                pickup_district,
                pickup_ward,
                pickup_village,
                pickup_landmark,
            )
            if missing:
                return Response(
                    {
                        "detail": "Send representative_id or a complete pickup address (country, region, district, ward, village, landmark).",
                        "missing": missing,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        total = 0
        note = request.data.get('customer_note') or ''
        if not isinstance(note, str):
            note = str(note)
        order = Order.objects.create(
            user=user,
            total_amount=0,
            customer_note=note,
            pickup_country=pickup_country,
            pickup_region=pickup_region,
            pickup_district=pickup_district,
            pickup_ward=pickup_ward,
            pickup_village=pickup_village,
            pickup_landmark=pickup_landmark,
        )
        for it in items:
            sid = it.get('service_id')
            qty = int(it.get('quantity', 1))
            try:
                dh = int(it.get('duration_hours', 1) or 1)
            except (TypeError, ValueError):
                dh = 1
            dh = max(1, min(dh, 9999))
            raw_note = it.get('line_note')
            if raw_note is None:
                raw_note = it.get('note', '')
            line_note = str(raw_note).strip()[:4000] if raw_note is not None else ''
            try:
                svc = Service.objects.get(pk=sid, is_active=True)
            except Service.DoesNotExist:
                order.delete()
                return Response({'detail': f'Service {sid} not found'}, status=400)
            price = svc.price
            OrderItem.objects.create(
                order=order,
                service=svc,
                quantity=qty,
                price=price,
                duration_hours=dh,
                line_note=line_note,
            )
            total += float(price) * qty

        order.total_amount = total
        order.representative = rep
        order.save()
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=201)


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        profile = getattr(user, 'profile', None)
        data['user'] = {
            'id': user.id,
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'email_verified': bool(profile and profile.email_verified_at),
            'profile': ProfileSerializer(profile).data if profile else {},
        }
        linked = Representative.objects.filter(
            linked_user=user, is_active=True
        ).values("id", "full_name").first()
        data["user"]["linked_representative"] = (
            dict(linked) if linked else None
        )
        return data


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


def _linked_representative_payload(user):
    linked = Representative.objects.filter(
        linked_user=user, is_active=True
    ).values("id", "full_name").first()
    return dict(linked) if linked else None


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):
    user = request.user
    # GET returns basic user + profile
    if request.method == 'GET':
        profile = getattr(user, 'profile', None)
        profile_data = ProfileSerializer(profile).data if profile else {}
        data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'email_verified': bool(profile and profile.email_verified_at),
            'profile': profile_data,
            'linked_representative': _linked_representative_payload(user),
        }
        return Response(data)

    if request.method == 'PUT':
        # accept form-data or json; update user and profile
        profile, _ = Profile.objects.get_or_create(user=user)
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if email is not None:
            old_email = (user.email or "").strip().lower()
            new_email = email.strip().lower()
            user.email = new_email
            user.username = new_email
            if new_email != old_email:
                profile.email_verified_at = None
        user.save()

        # update profile fields
        profile.gender = request.data.get('gender', profile.gender)
        profile.age_group = request.data.get('age_group', profile.age_group)
        profile.phone = request.data.get('phone', profile.phone)
        profile.city = request.data.get('city', profile.city)
        share = request.data.get('share_profile_data')
        if share is not None:
            profile.share_profile_data = str(share).lower() in ('1', 'true', 'yes')
        # handle avatar upload
        avatar = request.FILES.get('avatar')
        if avatar:
            profile.avatar = avatar
        profile.save()
        data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'email_verified': bool(profile and profile.email_verified_at),
            'profile': ProfileSerializer(profile).data,
            'linked_representative': _linked_representative_payload(user),
        }
        return Response(data)

    if request.method == 'DELETE':
        # delete the user account
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)




@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def representatives_nearby(request):
    try:
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        if lat is None or lng is None:
            return Response({'detail': 'lat and lng required'}, status=400)
        lat = float(lat)
        lng = float(lng)
    except Exception:
        return Response({'detail': 'invalid lat/lng'}, status=400)

    # Haversine distance calculation
    from math import radians, cos, sin, asin, sqrt

    def haversine(lat1, lon1, lat2, lon2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        km = 6371 * c
        return km

    reps = Representative.objects.filter(is_active=True)
    out = []
    for r in reps:
        try:
            d = haversine(lat, lng, float(r.latitude), float(r.longitude))
        except Exception:
            d = None
        ser = RepresentativeSerializer(r, context={'request': request}).data
        if d is not None:
            ser['distance'] = round(d, 3)
        out.append(ser)
    out = sorted([o for o in out if o.get('distance') is not None], key=lambda x: x['distance']) + [o for o in out if o.get('distance') is None]
    return Response(out)


class RepresentativeViewSet(viewsets.ModelViewSet):
    queryset = Representative.objects.all()
    serializer_class = RepresentativeSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    permission_classes = [PublicReadAdminWrite]


class PartnerTypeViewSet(viewsets.ModelViewSet):
    queryset = PartnerType.objects.all().order_by('name')
    serializer_class = PartnerTypeSerializer

    permission_classes = [PublicReadAdminWrite]

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs


class PartnershipViewSet(viewsets.ModelViewSet):
    queryset = Partnership.objects.all().order_by('-created_at')
    serializer_class = PartnershipSerializer

    def get_permissions(self):
        # Optional authentication for partner signup:
        # - guest users can submit POST
        # - authenticated users are auto-linked in perform_create
        # - GET list/detail: open (anonymous users see empty queryset from get_queryset)
        if self.request.method == 'POST':
            return [permissions.AllowAny()]
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        qs = super().get_queryset()
        if user and user.is_staff:
            return qs
        if user and user.is_authenticated:
            return qs.filter(user=user)
        return Partnership.objects.none()

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)
