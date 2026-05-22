"""
Production-oriented auth endpoints: registration + email OTP, password reset,
rate limiting (cache), and hashed single-use codes.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .email import (
    send_password_changed_email,
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)
from django.contrib.auth.hashers import make_password

from .models import EmailOTPChallenge, Profile
from .registration_cache import (
    REGISTER_CACHE_TTL,
    REGISTER_OTP_MAX_ATTEMPTS,
    delete_pending,
    gen_six_digit_otp,
    get_pending,
    increment_failed_attempts,
    otp_matches,
    save_pending,
)
from .serializers import (
    ProfileSerializer,
    RegisterResendSerializer,
    RegisterStartSerializer,
    RegisterVerifySerializer,
)

logger = logging.getLogger(__name__)

OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5
RESEND_MIN_INTERVAL = 60
RESEND_HOUR_LIMIT = 5
IP_COMBINED_HOUR_LIMIT = 40
RESET_TOKEN_MAX_AGE = 600

PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"
)

RESET_SIGN_SALT = "mpanzi-pwd-reset-ticket-v1"


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _email_valid(email: str) -> bool:
    try:
        validate_email(email)
    except DjangoValidationError:
        return False
    return True


def _strong_password(pw: str) -> bool:
    return bool(pw and PASSWORD_PATTERN.match(pw))


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "unknown")[:45]


def _hash_code(user_id: int, purpose: str, code: str) -> str:
    pepper = settings.SECRET_KEY.encode()
    raw = f"{user_id}|{purpose}|{code}".encode()
    return hashlib.sha256(pepper + raw).hexdigest()


def _codes_match(challenge: EmailOTPChallenge, code: str) -> bool:
    expect = _hash_code(challenge.user_id, challenge.purpose, code)
    return secrets.compare_digest(challenge.code_hash, expect)


def _gen_six_digit() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def _rate_incr(key: str, window_sec: int) -> int:
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_sec)
        return 1


def _rate_under_cap(key: str, cap: int, window_sec: int) -> bool:
    n = _rate_incr(key, window_sec)
    return n <= cap


def _invalidate_open_otps(user: User, purpose: str) -> None:
    now = timezone.now()
    EmailOTPChallenge.objects.filter(
        user=user, purpose=purpose, used_at__isnull=True
    ).update(used_at=now)


def _create_otp_challenge(user: User, purpose: str) -> str:
    _invalidate_open_otps(user, purpose)
    code = _gen_six_digit()
    EmailOTPChallenge.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash_code(user.id, purpose, code),
        expires_at=timezone.now() + OTP_TTL,
    )
    return code


def _latest_open_challenge(user: User, purpose: str) -> EmailOTPChallenge | None:
    return (
        EmailOTPChallenge.objects.filter(
            user=user,
            purpose=purpose,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )


def _user_api_dict(user: User) -> dict:
    profile = getattr(user, "profile", None)
    profile_data = ProfileSerializer(profile).data if profile else {}
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "name": f"{user.first_name} {user.last_name}".strip() or user.username,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "email_verified": bool(profile and profile.email_verified_at),
        "profile": profile_data,
    }


def _tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": _user_api_dict(user),
    }


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_register(request):
    """Store pending registration in cache and email a 6-digit OTP (no User row yet)."""
    ser = RegisterStartSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    email = ser.validated_data["email"]
    full_name = ser.validated_data["full_name"]
    password = ser.validated_data["password"]

    ip = _client_ip(request)
    if not _rate_under_cap(f"auth:reg:ip:{ip}", IP_COMBINED_HOUR_LIMIT, 3600):
        return Response(
            {"detail": "Too many attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    parts = full_name.split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""
    code = gen_six_digit_otp()
    password_hash = make_password(password)

    save_pending(
        email=email,
        username=email,
        password_hash=password_hash,
        first_name=first,
        last_name=last,
        otp_code=code,
    )

    send_verification_email(email, code, expires_minutes=REGISTER_CACHE_TTL // 60)

    return Response(
        {
            "detail": "Verification code sent to your email.",
            "email": email,
            "expires_in_seconds": REGISTER_CACHE_TTL,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_register_resend(request):
    ser = RegisterResendSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    email = ser.validated_data["email"]
    pending = get_pending(email)
    if not pending:
        return Response(
            {
                "detail": "Registration session expired. Please start registration again.",
                "error": "otp_expired",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username__iexact=email).exists() or User.objects.filter(
        email__iexact=email
    ).exists():
        delete_pending(email)
        return Response(
            {"email": ["An account with this email already exists."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sent_at = float(pending.get("sent_at") or 0)
    if sent_at and (timezone.now().timestamp() - sent_at) < RESEND_MIN_INTERVAL:
        return Response(
            {"detail": f"Please wait {RESEND_MIN_INTERVAL} seconds before resending."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not _rate_under_cap(f"auth:resend:reg:{email}", RESEND_HOUR_LIMIT, 3600):
        return Response(
            {"detail": "Too many resend attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    ip = _client_ip(request)
    if not _rate_under_cap(f"auth:reg:ip:{ip}", IP_COMBINED_HOUR_LIMIT, 3600):
        return Response(
            {"detail": "Too many attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    code = gen_six_digit_otp()
    save_pending(
        email=email,
        username=pending["username"],
        password_hash=pending["password"],
        first_name=pending.get("first_name", ""),
        last_name=pending.get("last_name", ""),
        otp_code=code,
        failed_attempts=0,
    )
    send_verification_email(email, code, expires_minutes=REGISTER_CACHE_TTL // 60)

    return Response(
        {
            "detail": "Verification code sent.",
            "email": email,
            "expires_in_seconds": REGISTER_CACHE_TTL,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_register_verify(request):
    ser = RegisterVerifySerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    email = ser.validated_data["email"]
    code = ser.validated_data["code"]

    if not _rate_under_cap(f"auth:verify:reg:{email}", 25, 3600):
        return Response(
            {"detail": "Too many verification attempts. Try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    pending = get_pending(email)
    if not pending:
        return Response(
            {
                "detail": "OTP has expired. Please register again.",
                "error": "otp_expired",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username__iexact=email).exists() or User.objects.filter(
        email__iexact=email
    ).exists():
        delete_pending(email)
        return Response(
            {"email": ["An account with this email already exists."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    otp_hash = pending.get("otp") or ""
    if not otp_matches(email, code, otp_hash):
        attempts = increment_failed_attempts(email)
        if attempts >= REGISTER_OTP_MAX_ATTEMPTS:
            delete_pending(email)
        return Response(
            {"detail": "Invalid OTP.", "error": "invalid_otp"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        user = User(
            username=pending["username"],
            email=pending["email"],
            first_name=pending.get("first_name", ""),
            last_name=pending.get("last_name", ""),
            is_active=True,
        )
        user.password = pending["password"]
        user.save()

        prof, _ = Profile.objects.select_for_update().get_or_create(user=user)
        prof.email_verified_at = timezone.now()
        prof.save(update_fields=["email_verified_at"])

    delete_pending(email)
    send_welcome_email(user.email)
    data = _tokens_for_user(user)
    return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_password_reset_request(request):
    email = _normalize_email(request.data.get("email", ""))
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not _email_valid(email):
        return Response({"email": ["Enter a valid email address."]}, status=status.HTTP_400_BAD_REQUEST)

    if not _rate_under_cap(f"auth:pwreq:ip:{_client_ip(request)}", IP_COMBINED_HOUR_LIMIT, 3600):
        return Response(
            {"detail": "Too many attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = User.objects.filter(username__iexact=email, is_active=True).first()
    if not user:
        return Response(
            {"detail": "Account not found. Please use a registered email."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _rate_under_cap(f"auth:resend:pw:{email}", RESEND_HOUR_LIMIT, 3600):
        return Response(
            {"detail": "Too many reset attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    last = EmailOTPChallenge.objects.filter(
        user=user, purpose=EmailOTPChallenge.PURPOSE_PASSWORD_RESET, used_at__isnull=True
    ).order_by("-created_at").first()
    if last and (timezone.now() - last.created_at).total_seconds() < RESEND_MIN_INTERVAL:
        return Response(
            {"detail": f"Please wait {RESEND_MIN_INTERVAL} seconds before requesting again."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    with transaction.atomic():
        code = _create_otp_challenge(user, EmailOTPChallenge.PURPOSE_PASSWORD_RESET)

    transaction.on_commit(lambda: send_password_reset_email(email, code))
    return Response(
        {
            "detail": "If an account exists, a reset code has been sent.",
            "email": email,
            "expires_in_seconds": int(OTP_TTL.total_seconds()),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_password_reset_resend(request):
    email = _normalize_email(request.data.get("email", ""))
    if not email:
        return Response({"detail": "Email required."}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(username__iexact=email, is_active=True).first()
    if not user:
        return Response({"detail": "If an account exists, a code has been sent."}, status=status.HTTP_200_OK)

    if not _rate_under_cap(f"auth:resend:pw:{email}", RESEND_HOUR_LIMIT, 3600):
        return Response(
            {"detail": "Too many resend attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    last = _latest_open_challenge(user, EmailOTPChallenge.PURPOSE_PASSWORD_RESET)
    if last and (timezone.now() - last.created_at).total_seconds() < RESEND_MIN_INTERVAL:
        return Response(
            {"detail": f"Please wait {RESEND_MIN_INTERVAL} seconds before resending."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    with transaction.atomic():
        code = _create_otp_challenge(user, EmailOTPChallenge.PURPOSE_PASSWORD_RESET)

    transaction.on_commit(lambda: send_password_reset_email(email, code))
    return Response(
        {"detail": "Reset code sent.", "expires_in_seconds": int(OTP_TTL.total_seconds())},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_password_reset_verify(request):
    email = _normalize_email(request.data.get("email", ""))
    code = (request.data.get("code") or "").strip().replace(" ", "")
    if not email or len(code) != 6 or not code.isdigit():
        return Response(
            {"detail": "Valid email and 6-digit code required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _rate_under_cap(f"auth:verify:pw:{email}", 25, 3600):
        return Response(
            {"detail": "Too many attempts. Try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = User.objects.filter(username__iexact=email, is_active=True).first()
    if not user:
        return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

    ch = _latest_open_challenge(user, EmailOTPChallenge.PURPOSE_PASSWORD_RESET)
    if not ch:
        return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

    if not _codes_match(ch, code):
        EmailOTPChallenge.objects.filter(pk=ch.pk).update(
            failed_attempts=F("failed_attempts") + 1
        )
        ch.refresh_from_db()
        if ch.failed_attempts >= OTP_MAX_ATTEMPTS:
            ch.used_at = timezone.now()
            ch.save(update_fields=["used_at"])
        return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

    ch.used_at = timezone.now()
    ch.save(update_fields=["used_at"])
    reset_token = signing.dumps({"u": user.id}, salt=RESET_SIGN_SALT)
    return Response(
        {"reset_token": reset_token, "detail": "Code verified. You may set a new password."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_password_reset_confirm(request):
    reset_token = request.data.get("reset_token") or ""
    password = request.data.get("password") or ""
    confirm = request.data.get("confirm_password") or ""

    if not reset_token:
        return Response({"detail": "Reset token required."}, status=status.HTTP_400_BAD_REQUEST)
    if password != confirm:
        return Response(
            {"confirm_password": ["Passwords do not match."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not _strong_password(password):
        return Response(
            {
                "password": [
                    "Must be at least 8 characters and include uppercase, lowercase, a number, and a special character."
                ]
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        payload = signing.loads(reset_token, salt=RESET_SIGN_SALT, max_age=RESET_TOKEN_MAX_AGE)
        uid = int(payload["u"])
    except Exception:
        return Response(
            {"detail": "Invalid or expired reset session. Please start again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(pk=uid, is_active=True)
    except User.DoesNotExist:
        return Response(
            {"detail": "Invalid or expired reset session. Please start again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=["password"])
        _invalidate_open_otps(user, EmailOTPChallenge.PURPOSE_PASSWORD_RESET)

    transaction.on_commit(lambda: send_password_changed_email(user.email))
    return Response(
        {"detail": "Password updated successfully. You can sign in with your new password."},
        status=status.HTTP_200_OK,
    )


# Backwards-compatible path `/register/` used by older clients — same as auth_register.
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register_view(request):
    return auth_register(request)
