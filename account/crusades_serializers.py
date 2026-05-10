"""Serializers for Crusade APIs (Flutter app)."""

from urllib.parse import urlparse, parse_qs

from rest_framework import serializers

from .models import (
    Crusade,
    CrusadeGalleryItem,
    CrusadeReport,
    CrusadeTestimony,
    CrusadeVideo,
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


class CrusadeReportSerializer(serializers.ModelSerializer):
    inline_images = serializers.SerializerMethodField()

    class Meta:
        model = CrusadeReport
        fields = [
            'id',
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


class CrusadeTestimonySerializer(serializers.ModelSerializer):
    class Meta:
        model = CrusadeTestimony
        fields = [
            'id',
            'crusade_id',
            'name',
            'image',
            'testimony',
            'miracle_type',
            'order',
        ]


class CrusadeGalleryItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CrusadeGalleryItem
        fields = [
            'id',
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


class CrusadeVideoSerializer(serializers.ModelSerializer):
    youtube_id = serializers.SerializerMethodField()

    class Meta:
        model = CrusadeVideo
        fields = [
            'id',
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


class CrusadeSerializer(serializers.ModelSerializer):
    banner_image = serializers.SerializerMethodField()

    class Meta:
        model = Crusade
        fields = [
            'id',
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


class CrusadeDetailSerializer(CrusadeSerializer):
    reports = CrusadeReportSerializer(many=True, read_only=True)
    testimonies = CrusadeTestimonySerializer(many=True, read_only=True)
    gallery = CrusadeGalleryItemSerializer(
        source='gallery_items',
        many=True,
        read_only=True,
    )
    videos = CrusadeVideoSerializer(many=True, read_only=True)

    class Meta(CrusadeSerializer.Meta):
        fields = CrusadeSerializer.Meta.fields + [
            'reports',
            'testimonies',
            'gallery',
            'videos',
        ]
