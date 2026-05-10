from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import SermonViewSet, AnnouncementViewSet, NewsViewSet, TimetableViewSet, BookViewSet, FeedbackViewSet, ServiceViewSet, AdminServiceViewSet, OrderViewSet, register_view, me_view, RepresentativeViewSet, representatives_nearby, PartnerTypeViewSet, PartnershipViewSet, DevotionalViewSet, CrusadeViewSet
from .views import InitiatePaymentAPIView, AzamPayWebhookAPIView, PaymentStatusAPIView

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
router.register(r'crusades', CrusadeViewSet, basename='crusade')

urlpatterns = [
    path('', include(router.urls)),
    path('representatives/nearby/', representatives_nearby, name='representatives-nearby'),
    path('register/', register_view, name='register'),
    path('me/', me_view, name='me'),
    path('payments/initiate/', InitiatePaymentAPIView.as_view(), name='payments-initiate'),
    path('payments/webhook/', AzamPayWebhookAPIView.as_view(), name='payments-webhook'),
    path('payments/webhook', AzamPayWebhookAPIView.as_view(), name='payments-webhook-noslash'),
    path('payments/status/<int:order_id>/', PaymentStatusAPIView.as_view(), name='payments-status'),
]
