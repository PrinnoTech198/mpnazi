"""
HTTP caching helpers for read-heavy list/detail APIs.

Enables Flutter clients to send If-None-Match and receive 304 when data unchanged,
cutting bandwidth and JSON parse work on background sync.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from django.utils.cache import patch_response_headers
from rest_framework.response import Response


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))


def compute_etag_from_payload(data: Any) -> str:
    """Weak ETag from serialized response body."""
    digest = hashlib.sha256(_stable_json(data).encode("utf-8")).hexdigest()[:32]
    return f'W/"{digest}"'


def list_etag_from_queryset(queryset, extra: str = "") -> str:
    """
    Cheaper ETag for paginated lists: max(timestamp) + count + filter fingerprint.
    """
    model = queryset.model
    ts_field = None
    for name in ("updated_at", "modified", "created_at", "date", "devotion_date"):
        if hasattr(model, name):
            ts_field = name
            break
    max_ts = ""
    if ts_field:
        row = queryset.order_by(f"-{ts_field}").values_list(ts_field, flat=True).first()
        max_ts = str(row) if row is not None else ""
    count = queryset.count()
    raw = f"{model._meta.label}:{count}:{max_ts}:{extra}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f'W/"{digest}"'


class _CacheHeadersMixin:
    cache_max_age = 120
    etag_from_queryset = True

    def _etag_for_list(self, queryset, response_data) -> str:
        if self.etag_from_queryset:
            q = self.filter_queryset(queryset)
            extra = self.request.get_full_path() if self.request else ""
            return list_etag_from_queryset(q, extra=extra)
        return compute_etag_from_payload(response_data)

    def _etag_for_detail(self, data) -> str:
        return compute_etag_from_payload(data)

    def _add_cache_headers(self, response: Response, etag: str) -> Response:
        response["ETag"] = etag
        patch_response_headers(response, cache_timeout=self.cache_max_age)
        response["Cache-Control"] = f"private, max-age={self.cache_max_age}"
        return response

    def _not_modified_if_match(self, etag: str) -> bool:
        inm = (self.request.META.get("HTTP_IF_NONE_MATCH") or "").strip()
        if not inm:
            return False

        def norm(v: str) -> str:
            return v.replace("W/", "").strip('"')

        return norm(inm) == norm(etag)


class ListConditionalGetMixin(_CacheHeadersMixin):
    """ETag + 304 on list only — safe with custom retrieve (e.g. view counters)."""

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data

        etag = self._etag_for_list(queryset, data)
        if self._not_modified_if_match(etag):
            return Response(status=304)

        if page is not None:
            response = self.get_paginated_response(serializer.data)
        else:
            response = Response(data)
        return self._add_cache_headers(response, etag)


class ConditionalGetMixin(ListConditionalGetMixin):
    """List + retrieve caching."""

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        etag = self._etag_for_detail(data)
        if self._not_modified_if_match(etag):
            return Response(status=304)
        response = Response(data)
        return self._add_cache_headers(response, etag)
