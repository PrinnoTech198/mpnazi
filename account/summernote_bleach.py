"""
django-summernote 0.8.20 calls bleach.clean(..., styles=...) which bleach 5+ removed.

Pin bleach<5 in requirements.txt. This patch also adapts summernote when bleach 5
is present (e.g. stale lockfiles) so production admin saves do not 500.
"""
from __future__ import annotations

import inspect
import logging

logger = logging.getLogger(__name__)


def apply_summernote_bleach_compat() -> None:
    import bleach
    from django.db import models
    from django.forms import fields as form_fields
    from django_summernote import fields as sn_fields
    from django_summernote.settings import ALLOWED_TAGS, ATTRIBUTES, STYLES

    if "styles" in inspect.signature(bleach.clean).parameters:
        return

    try:
        from bleach.css_sanitizer import CSSSanitizer
    except ImportError:
        logger.error(
            "bleach 5+ is installed but css_sanitizer is unavailable; "
            "pin bleach<5 in requirements.txt for django-summernote"
        )
        return

    css = CSSSanitizer(allowed_css_properties=list(STYLES))

    def _clean_html(value: str | None) -> str | None:
        if value is None:
            return None
        return bleach.clean(
            value,
            tags=ALLOWED_TAGS,
            attributes=ATTRIBUTES,
            css_sanitizer=css,
        )

    def form_to_python(self, value):
        value = form_fields.CharField.to_python(self, value)
        return _clean_html(value)

    def field_to_python(self, value):
        value = models.TextField.to_python(self, value)
        return _clean_html(value)

    sn_fields.SummernoteTextFormField.to_python = form_to_python
    sn_fields.SummernoteTextField.to_python = field_to_python
    logger.info("Applied django-summernote bleach 5+ compatibility patch")
