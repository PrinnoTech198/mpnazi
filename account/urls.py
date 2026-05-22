from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import SermonViewSet, AnnouncementViewSet, NewsViewSet, TimetableViewSet, BookViewSet, FeedbackViewSet, ServiceViewSet, AdminServiceViewSet, OrderViewSet, me_view, RepresentativeViewSet, representatives_nearby, PartnerTypeViewSet, PartnershipViewSet, DevotionalViewSet, CrusadeViewSet, EventViewSet
from .auth_views import (
    auth_register,
    auth_register_resend,
    auth_register_verify,
    auth_password_reset_request,
    auth_password_reset_resend,
    auth_password_reset_verify,
    auth_password_reset_confirm,
    register_view,
)
from .payment_views import (
    LegacyAzamPayWebhookAPIView,
    PartnershipPaymentInitiateAPIView,
    PartnershipPaymentReportAPIView,
    PartnershipPaymentStatusAPIView,
)

router = DefaultRouter()
router.register(r'sermons', SermonViewSet, basename='sermon')
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'news', NewsViewSet, basename='news')
router.register(r'timetable', TimetableViewSet, basename='timetable')
router.register(r'books', BookViewSet, basename='book')
router.register(r'feedback', FeedbackViewSet, basename='feedback')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'admin/services', AdminServiceViewSet, basename='admin-service')
router.register(r'representatives', RepresentativeViewSet, basename='representative')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'partner-types', PartnerTypeViewSet, basename='partner-type')
router.register(r'partnerships', PartnershipViewSet, basename='partnership')
router.register(r'devotionals', DevotionalViewSet, basename='devotional')
router.register(r'events', EventViewSet, basename='event')
router.register(r'crusades', CrusadeViewSet, basename='crusade')

urlpatterns = [
    path('', include(router.urls)),
    path('representatives/nearby/', representatives_nearby, name='representatives-nearby'),
    path('register/', register_view, name='register'),
    path('auth/register/', auth_register, name='auth-register'),
    path('auth/register/resend/', auth_register_resend, name='auth-register-resend'),
    path('auth/register/verify/', auth_register_verify, name='auth-register-verify'),
    path('auth/password-reset/request/', auth_password_reset_request, name='auth-password-reset-request'),
    path('auth/password-reset/resend/', auth_password_reset_resend, name='auth-password-reset-resend'),
    path('auth/password-reset/verify/', auth_password_reset_verify, name='auth-password-reset-verify'),
    path('auth/password-reset/confirm/', auth_password_reset_confirm, name='auth-password-reset-confirm'),
    path('me/', me_view, name='me'),
    path('admin/reports/partnership-payments/', PartnershipPaymentReportAPIView.as_view(), name='admin-reports-partnership-payments'),
    path('payments/partnership/initiate/', PartnershipPaymentInitiateAPIView.as_view(), name='payments-partnership-initiate'),
    path('payments/partnership/status/<int:payment_id>/', PartnershipPaymentStatusAPIView.as_view(), name='payments-partnership-status'),
    path('payments/webhook/', LegacyAzamPayWebhookAPIView.as_view(), name='payments-webhook'),
    path('payments/webhook', LegacyAzamPayWebhookAPIView.as_view(), name='payments-webhook-noslash'),
]
