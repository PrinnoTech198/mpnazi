from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from .models import DeviceToken, NotificationLog

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_CACHE_KEY = "fcm_access_token_v1"
FCM_CACHE_TTL_SECONDS = 55 * 60  # 55 minutes (token ~1h)


def _service_account_credentials():
    raw = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", None) or ""
    raw = raw.strip()
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set (paste the service account JSON object as a string)."
        )
    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(
        info,
        scopes=[FCM_SCOPE],
    )


def get_fcm_access_token() -> str:
    cached = cache.get(FCM_CACHE_KEY)
    if cached:
        return cached

    creds = _service_account_credentials()
    creds.refresh(GoogleAuthRequest())
    token = creds.token
    if not token:
        raise RuntimeError("FCM OAuth2 refresh returned no access token.")
    cache.set(FCM_CACHE_KEY, token, FCM_CACHE_TTL_SECONDS)
    return token


def _invalidate_token_cache() -> None:
    cache.delete(FCM_CACHE_KEY)


def _fcm_data_dict(data: dict[str, Any] | None) -> dict[str, str]:
    """FCM `data` payload values must be strings."""
    out: dict[str, str] = {}
    if not data:
        return out
    for k, v in data.items():
        if v is None:
            continue
        key = str(k)
        if isinstance(v, (dict, list)):
            out[key] = json.dumps(v, separators=(",", ":"))
        else:
            out[key] = str(v)
    return out


def _send_single_message(
    access_token: str,
    device_token: str,
    title: str,
    body: str,
    data_strings: dict[str, str],
) -> tuple[int, dict[str, Any]]:
    project_id = getattr(settings, "FCM_PROJECT_ID", None) or ""
    project_id = str(project_id).strip()
    if not project_id:
        raise RuntimeError("FCM_PROJECT_ID is not set.")

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    message: dict[str, Any] = {
        "token": device_token,
        "android": {"priority": "HIGH"},
        "apns": {
            "headers": {"apns-priority": "10"},
            "payload": {
                "aps": {
                    "sound": "default",
                    "content-available": 1,
                }
            },
        },
    }
    if title or body:
        message["notification"] = {"title": title, "body": body or " "}
    if data_strings:
        message["data"] = data_strings

    payload = {"message": message}
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    try:
        parsed = resp.json() if resp.content else {}
    except json.JSONDecodeError:
        parsed = {"raw": resp.text}
    return resp.status_code, parsed if isinstance(parsed, dict) else {"raw": parsed}


def _should_delete_invalid_token(status_code: int, body: dict[str, Any]) -> bool:
    if status_code == 404:
        return True
    if status_code != 400:
        return False
    err = body.get("error") or {}
    details = err.get("details") if isinstance(err, dict) else None
    if isinstance(details, list):
        for d in details:
            if not isinstance(d, dict):
                continue
            etype = (d.get("@type") or d.get("type") or "").lower()
            if "invalidargument" in etype or "unregistered" in etype:
                return True
            err_info = d.get("errorCode") or d.get("reason") or ""
            if isinstance(err_info, str) and err_info.upper() in (
                "UNREGISTERED",
                "INVALID_ARGUMENT",
            ):
                return True
    text = json.dumps(body).upper()
    return "UNREGISTERED" in text or "NOT_FOUND" in text and "REGISTRATION" in text


def send_push(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> None:
    """
    Send FCM HTTP v1 notification to each device token (individual sends for per-token logging).
    """
    if not tokens:
        return

    data_strings = _fcm_data_dict(data)
    access_token = get_fcm_access_token()

    for device_token in tokens:
        dt = (device_token or "").strip()
        if not dt:
            continue
        try:
            status, resp_body = _send_single_message(
                access_token, dt, title, body, data_strings
            )
        except requests.RequestException as exc:
            logger.exception("FCM network error for token suffix …%s", dt[-8:])
            NotificationLog.objects.create(
                token=dt,
                title=title,
                body=body,
                data=data or {},
                status=NotificationLog.STATUS_FAILED,
                error_message=str(exc),
            )
            continue

        if status == 200:
            name = ""
            if isinstance(resp_body, dict):
                name = str(resp_body.get("name") or "")
            NotificationLog.objects.create(
                token=dt,
                title=title,
                body=body,
                data=data or {},
                status=NotificationLog.STATUS_SENT,
                fcm_message_id=name[:512],
            )
            continue

        if status == 401:
            logger.warning("FCM 401 — refreshing OAuth token and retrying once.")
            _invalidate_token_cache()
            access_token = get_fcm_access_token()
            try:
                status, resp_body = _send_single_message(
                    access_token, dt, title, body, data_strings
                )
            except requests.RequestException as exc:
                NotificationLog.objects.create(
                    token=dt,
                    title=title,
                    body=body,
                    data=data or {},
                    status=NotificationLog.STATUS_FAILED,
                    error_message=str(exc),
                )
                continue
            if status == 200:
                name = str(resp_body.get("name") or "") if isinstance(resp_body, dict) else ""
                NotificationLog.objects.create(
                    token=dt,
                    title=title,
                    body=body,
                    data=data or {},
                    status=NotificationLog.STATUS_SENT,
                    fcm_message_id=name[:512],
                )
                continue

        err_text = json.dumps(resp_body)[:8000]
        NotificationLog.objects.create(
            token=dt,
            title=title,
            body=body,
            data=data or {},
            status=NotificationLog.STATUS_FAILED,
            error_message=f"HTTP {status}: {err_text}",
        )

        if _should_delete_invalid_token(status, resp_body if isinstance(resp_body, dict) else {}):
            deleted, _ = DeviceToken.objects.filter(token=dt).delete()
            if deleted:
                logger.info("Removed invalid FCM device token (suffix …%s)", dt[-8:])


def all_device_tokens() -> list[str]:
    return list(
        DeviceToken.objects.order_by("-updated_at").values_list("token", flat=True)[:5000]
    )


def user_device_tokens(user_id: int) -> list[str]:
    """FCM tokens registered for a specific authenticated user."""
    if not user_id:
        return []
    return list(
        DeviceToken.objects.filter(user_id=user_id)
        .order_by("-updated_at")
        .values_list("token", flat=True)[:50]
    )
