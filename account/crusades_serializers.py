"""Serializers for unified Event APIs.

The legacy Crusade serializer names are kept as aliases at the bottom so
existing imports and `/crusades/` responses remain compatible.
"""

from urllib.parse import urlparse, parse_qs

from rest_framework import serializers

from .models import (
    Event,
    EventGalleryItem,
    EventReport,
    EventTestimony,
    EventVideo,
)


def _youtube_id_from_url(url: str) -> str:
    if not url:
        return ''
    try:
        if 'youtu.be/' in url:
            return url.split('youtu.be/')[-1].split('?')[0].strip()
        parsed = urlparse(url)
        if parsed.hostname and 'youtube' in (parsed.hostname or ''):
            qs = parse_qs(parsed.query)
            if 'v' in qs:
                return qs['v'][0]
            parts = [p for p in parsed.path.split('/') if p]
            if parts:
                return parts[-1]
    except Exception:
        pass
    return ''


def _absolute_media_url(request, url: str) -> str:
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if request:
        try:
            return request.build_absolute_uri(url)
        except Exception:
            pass
    return url


class EventReportSerializer(serializers.ModelSerializer):
    inline_images = serializers.SerializerMethodField()
    crusade_id = serializers.IntegerField(source='event_id', read_only=True)
    event_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = EventReport
        fields = [
            'id',
            'event_id',
            'crusade_id',
            'title',
            'day_label',
            'body',
            'inline_images',
            'order',
        ]

    def get_inline_images(self, obj):
        request = self.context.get('request')
        if obj.image:
            try:
                u = obj.image.url
            except Exception:
                u = ''
            if u:
                return [_absolute_media_url(request, u)]
        return []


class EventTestimonySerializer(serializers.ModelSerializer):
    crusade_id = serializers.IntegerField(source='event_id', read_only=True)
    event_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = EventTestimony
        fields = [
            'id',
            'event_id',
            'crusade_id',
            'name',
            'image',
            'testimony',
            'miracle_type',
            'order',
        ]


class EventGalleryItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    crusade_id = serializers.IntegerField(source='event_id', read_only=True)
    event_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = EventGalleryItem
        fields = [
            'id',
            'event_id',
            'crusade_id',
            'image_url',
            'is_video',
            'video_url',
            'order',
        ]

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            try:
                u = obj.image.url
            except Exception:
                u = ''
            return _absolute_media_url(request, u)
        return ''


class EventVideoSerializer(serializers.ModelSerializer):
    youtube_id = serializers.SerializerMethodField()
    crusade_id = serializers.IntegerField(source='event_id', read_only=True)
    event_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = EventVideo
        fields = [
            'id',
            'event_id',
            'crusade_id',
            'title',
            'youtube_url',
            'youtube_id',
            'order',
        ]

    def get_youtube_id(self, obj):
        if obj.youtube_id:
            return obj.youtube_id
        return _youtube_id_from_url(obj.youtube_url or '')


class EventSerializer(serializers.ModelSerializer):
    banner_image = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id',
            'event_type',
            'title',
            'theme',
            'description',
            'banner_image',
            'city',
            'country',
            'speaker',
            'start_date',
            'end_date',
            'start_time',
            'end_time',
            'livestream_url',
            'souls_saved',
            'miracles_count',
            'attendance_count',
            'is_live',
            'published',
            'live_attendance',
            'prayer_comments',
            'online_nations',
            'created_at',
            'updated_at',
        ]

    def get_banner_image(self, obj):
        request = self.context.get('request')
        if obj.banner_image:
            try:
                u = obj.banner_image.url
            except Exception:
                u = ''
            return _absolute_media_url(request, u)
        return ''


class EventDetailSerializer(EventSerializer):
    reports = EventReportSerializer(many=True, read_only=True)
    testimonies = EventTestimonySerializer(many=True, read_only=True)
    gallery = EventGalleryItemSerializer(
        source='gallery_items',
        many=True,
        read_only=True,
    )
    videos = EventVideoSerializer(many=True, read_only=True)

    class Meta(EventSerializer.Meta):
        fields = EventSerializer.Meta.fields + [
            'reports',
            'testimonies',
            'gallery',
            'videos',
        ]


CrusadeReportSerializer = EventReportSerializer
CrusadeTestimonySerializer = EventTestimonySerializer
CrusadeGalleryItemSerializer = EventGalleryItemSerializer
CrusadeVideoSerializer = EventVideoSerializer
CrusadeSerializer = EventSerializer
CrusadeDetailSerializer = EventDetailSerializer
