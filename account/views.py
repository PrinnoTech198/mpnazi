from rest_framework import viewsets, filters
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
from .models import Service, Order, OrderItem, Representative
from .serializers import AnnouncementSerializer, NewsSerializer, NewsImageSerializer, TimetableSerializer, BookSerializer, FeedbackSerializer, ServiceSerializer, OrderSerializer, OrderItemSerializer, RepresentativeSerializer

from rest_framework import permissions, parsers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import authentication_classes
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from .models import Profile
from .serializers import ProfileSerializer
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from uuid import uuid4
from .services.azampay import AzamPayClient
from .models import Payment, Order
from .serializers import PaymentSerializer, OrderStatusSerializer
from django.conf import settings
import hmac
import hashlib
import json
import logging
import requests  # ← Hakikisha hii ipo juu ya file
from requests.exceptions import ReadTimeout, RequestException

logger = logging.getLogger(__name__)

# Note: AzamPayClient will be instantiated per-request to avoid import-time side effects



class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class SermonViewSet(viewsets.ModelViewSet):
    """Sermons API - list, retrieve for public; CRUD for admin."""
    queryset = Sermon.objects.all()
    serializer_class = SermonSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'sermon_type', 'featured', 'published']
    search_fields = ['title', 'description', 'speaker']
    ordering_fields = ['date', 'views_count', 'created_at']
    ordering = ['-date']
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

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


class AnnouncementViewSet(viewsets.ModelViewSet):
    """Admin can create/update/delete. Public can read/list active announcements."""
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_permissions(self):
        # Safe methods (GET, HEAD, OPTIONS) are allowed to anyone.
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        # Unsafe methods require admin/staff
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        # For anonymous/public (non-admin) users, only return active ones
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs.order_by('-created_at')


class NewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all()
    serializer_class = NewsSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

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

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

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


class BookViewSet(viewsets.ModelViewSet):
    """Books listing and admin CRUD."""
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        # Only return active books for non-admin users
        user = getattr(self.request, 'user', None)
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs.order_by('-created_at')


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



class InitiatePaymentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        logger.info('InitiatePayment called by user=%s data=%s', getattr(request.user, 'id', None), data)
        order_id = data.get('order_id')
        method = data.get('payment_method')
        phone = data.get('phone_number')
        if not order_id or not method:
            return Response({'detail': 'order_id and payment_method required'}, status=400)

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            logger.warning('Order not found: %s for user %s', order_id, request.user)
            return Response({'detail': 'Order not found'}, status=404)

        if order.status not in (Order.STATUS_PENDING, Order.STATUS_FAILED):
            return Response({'detail': 'Order not in a payable state'}, status=400)

        external_ref = str(uuid4())

        try:
            client = AzamPayClient()
        except Exception as e:
            logger.exception('Failed to create AzamPayClient: %s', e)
            return Response({'detail': f'Payment client init failed: {e}'}, status=500)

        try:
            # Ensure amounts are serializable (convert Decimal to string)
            amount = order.total_amount
            try:
                # Decimal -> str
                amount_to_send = str(amount)
            except Exception:
                amount_to_send = amount
            if method == Order.PAYMENT_MOBILE:

                if not phone:
                    return Response({
                        'detail': 'phone_number required'
                    }, status=400)

                # CREATE PAYMENT FIRST
                payment = Payment.objects.create(
                    order=order,
                    amount=order.total_amount,
                    external_reference=external_ref,
                    status=Payment.STATUS_PENDING
                )

                # UPDATE ORDER
                order.external_reference = external_ref
                order.payment_method = Order.PAYMENT_MOBILE
                order.status = Order.STATUS_PROCESSING
                order.save()
                try:

                    resp = client.initiate_mobile_money(
                        amount_to_send,
                        phone,
                        external_ref
                    )

                    provider_tx_id = (
                        resp.get('transactionId')
                        or resp.get('transaction_id')
                        or resp.get('tx_id')
                    )

                    payment.provider_transaction_id = provider_tx_id
                    payment.raw_response = resp
                    payment.save()

                    order.transaction_id = provider_tx_id
                    order.save()

                    return Response({
                        'success': True,
                        'transaction_id': external_ref,
                        'message': 'Payment request sent. Waiting confirmation.',
                        'messageCode': 0,
                    }, status=200)

                except ReadTimeout:

                    logger.warning(
                        "AzamPay timeout but webhook may still arrive"
                    )

                    return Response({
                        'success': True,
                        'message': 'Payment request sent. Waiting confirmation.',
                        'status': 'PROCESSING'
                    }, status=200)

                except RequestException as e:

                    payment.status = Payment.STATUS_FAILED
                    payment.save()

                    order.status = Order.STATUS_FAILED
                    order.save()

                    logger.exception("Payment failed")

                    return Response({
                        'detail': str(e)
                    }, status=500)

            # if method == Order.PAYMENT_MOBILE:
            #     if not phone:
            #         return Response({'detail': 'phone_number required for mobile money'}, status=400)
            #     resp = client.initiate_mobile_money(amount_to_send, phone, external_ref)
            #     transaction_id = resp.get('transactionId') or resp.get('transaction_id') or resp.get('tx_id')
            #     provider_tx_id = resp.get('transactionId')
            #     #payment = Payment.objects.create(order=order, amount=order.total_amount, transaction_id=transaction_id, raw_response=resp)
            #     payment = Payment.objects.create(order=order, amount=order.total_amount, external_reference=external_ref, provider_transaction_id=provider_tx_id, raw_response=resp)
            #     order.transaction_id = provider_tx_id
            #     order.external_reference = external_ref
            #     order.payment_method = Order.PAYMENT_MOBILE
            #     order.status = Order.STATUS_PROCESSING
            #     order.save()
            #     return Response({'provider_response': resp}, status=200)

            elif method == Order.PAYMENT_CARD:
                resp = client.initiate_card(amount_to_send, external_ref)
                checkout_url = resp.get('checkout_url') or resp.get('redirect_url')
                transaction_id = resp.get('transactionId') or resp.get('transaction_id') or resp.get('tx_id')
                payment = Payment.objects.create(order=order, amount=order.total_amount, external_reference=external_ref, provider_transaction_id=provider_tx_id, raw_response=resp)
                order.transaction_id = provider_tx_id
                order.external_reference = external_ref
                order.payment_method = Order.PAYMENT_CARD
                order.status = Order.STATUS_PROCESSING
                order.save()
                return Response({'checkout_url': checkout_url, 'provider_response': resp}, status=200)

            else:
                return Response({'detail': 'Unsupported payment_method'}, status=400)

        except Exception as e:
            logger.exception('Payment initiation failed for order=%s user=%s: %s', order_id, request.user, e)
            # try to surface a readable message
            msg = str(e)
            return Response({'detail': f'Payment initiation failed: {msg}'}, status=500)

# @method_decorator(csrf_exempt, name='dispatch')
# class AzamPayWebhookAPIView(APIView):

#     permission_classes = [permissions.AllowAny]
#     parser_classes = [JSONParser]

#     def post(self, request):

#         print("WEBHOOK RECEIVED =>", request.data)

#         payload = request.data

#         # HANDLE ALL POSSIBLE FIELD NAMES
#         external_ref = (
#             payload.get('external_reference')
#             or payload.get('externalreference')
#             or payload.get('reference')
#         )

#         tx_id = (
#             payload.get('transactionId')
#             or payload.get('transaction_id')
#             or payload.get('tx_id')
#             or payload.get('transid')
#         )

#         # status_str = (
#         #     payload.get('status')
#         #     or payload.get('payment_status')
#         #     or payload.get('transactionStatus')
#         #     or payload.get('transactionstatus')
#         #     or ''
#         # )
#         if status_str == "success":

#             payment.status = Payment.STATUS_SUCCESS
#             payment.raw_response = payload
#             payment.save()

#             order = payment.order
#             order.status = Order.STATUS_PAID
#             order.save()

#             return Response({"success": True}, status=200)

#         print("EXTERNAL REF =>", external_ref)
#         print("TX ID =>", tx_id)
#         print("STATUS =>", status_str)

#         payment = None
#         print("PAYMENT SAVED =>", payment.id)
#         print("EXTERNAL REF SAVED =>", payment.external_reference)
#         print("PROVIDER TX ID =>", payment.provider_transaction_id)

#         # FIND PAYMENT
#         if external_ref:
#             payment = Payment.objects.filter(order__external_reference=external_ref).first()
            

#         if not payment and tx_id:
#             payment = Payment.objects.filter(provider_transaction_id=tx_id).first()

#         if not payment and external_ref:
#             payment = Payment.objects.filter(external_reference=external_ref).first()


#         #     payment = Payment.objects.filter(
#         #         order__external_reference=external_ref
#         #     ).first()

#         # if not payment and tx_id:

#         #     payment = Payment.objects.filter(
#         #         transaction_id=tx_id
#         #     ).first()

#         print("MATCHED PAYMENT =>", payment)

#         # PAYMENT NOT FOUND
#         if not payment:

#             logger.warning(
#                 'Webhook received for unknown payment: %s',
#                 payload
#             )

#             return Response({
#                 'detail': 'Payment not found'
#             }, status=404)

#         # SAVE RAW RESPONSE
#         payment.raw_response = payload

#         # SUCCESS
#         if status_str.lower() in (
#             'success',
#             'successful',
#             'completed',
#             'paid'
#         ):

#             payment.status = Payment.STATUS_SUCCESS
#             payment.save()

#             order = payment.order
#             order.status = Order.STATUS_PAID
#             order.save()

#             print("PAYMENT SUCCESSFULLY UPDATED")

#             return Response({
#                 'success': True
#             })

#         # FAILED
#         payment.status = Payment.STATUS_FAILED
#         payment.save()

#         order = payment.order
#         order.status = Order.STATUS_FAILED
#         order.save()

#         print("PAYMENT FAILED")

#         return Response({
#             'success': False
#         })


@method_decorator(csrf_exempt, name='dispatch')
class AzamPayWebhookAPIView(APIView):

    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):

        try:

            print("WEBHOOK RECEIVED =>", request.data)

            payload = request.data

            # =========================
            # GET REFERENCES
            # =========================

            external_ref = (
                payload.get('externalreference')
                or payload.get('external_reference')
                or payload.get('reference')
            )

            tx_id = (
                payload.get('transid')
                or payload.get('transactionId')
                or payload.get('transaction_id')
                or payload.get('tx_id')
                
            )

            status_str = (
                payload.get('transactionStatus')
                or payload.get('status')
                or payload.get('payment_status')
                or payload.get('transactionstatus')
                or ''
            ).lower()


            

            print("EXTERNAL REF =>", external_ref)
            print("TX ID =>", tx_id)
            print("STATUS =>", status_str)

            # =========================
            # FIND PAYMENT
            # =========================
            import time
            payment = None

            # FIND BY EXTERNAL REFERENCE
            for attempt in range(3):
                if external_ref:
                    payment = Payment.objects.filter(
                        external_reference=external_ref
                    ).first()
                if not payment and tx_id:

                    payment = Payment.objects.filter(
                        provider_transaction_id=tx_id
                    ).first()
                if payment:
                    break
                print(f"ATTEMPT {attempt + 1}: Payment not found yet, waiting...")
                time.sleep(1)# Wait before retrying
            print("MATCHED PAYMENT =>", payment)
            # FIND BY PROVIDER TX ID
       
            # =========================
            # PAYMENT NOT FOUND
            # =========================

            if not payment:

                logger.warning(
                    "Webhook received for unknown payment: %s",
                    payload
                )

                return Response({
                    "success": True,
                    "message": "Payment not found"
                }, status=200)

            # =========================
            # SAVE RAW RESPONSE
            # =========================

            payment.raw_response = payload
            payment.provider_transaction_id = tx_id or payment.provider_transaction_id
            # =========================
            # SUCCESS PAYMENT
            # =========================

            if status_str in (
                'success',
                'successful',
                'completed',
                'paid'
                ):

                payment.status = Payment.STATUS_SUCCESS
                payment.save()

                order = payment.order
                order.status = Order.STATUS_PAID
                order.save()

                print("PAYMENT SUCCESSFULLY UPDATED")

                return Response({
                    "success": True,
                    "message": "Payment successful"
                }, status=200)

            # =========================
            # FAILED PAYMENT
            # =========================

            payment.status = Payment.STATUS_FAILED
            payment.save()

            order = payment.order
            order.status = Order.STATUS_FAILED
            order.save()

            print("PAYMENT FAILED")

            return Response({
                "success": False,
                "message": "Payment failed"
            }, status=200)

        except Exception as e:

            print("WEBHOOK ERROR =>", str(e))

            logger.exception(
                "AzamPay webhook error: %s",
                str(e)
            )

            return Response({
                "success": False,
                "message": str(e)
            }, status=500)
# @method_decorator(csrf_exempt, name='dispatch')
# class AzamPayWebhookAPIView(APIView):
#     permission_classes = [permissions.AllowAny]
#     parser_classes = [JSONParser]

#     def post(self, request):
#         # Optional webhook signature verification
#         secret = getattr(settings, 'AZAMPAY_WEBHOOK_SECRET', None)
#         if secret:
#             # Common header names providers use (case-insensitive via WSGI keys)
#             signature = (
#                 request.META.get('HTTP_X_AZAMPAY_SIGNATURE')
#                 or request.META.get('HTTP_X_SIGNATURE')
#                 or request.META.get('HTTP_X_HUB_SIGNATURE')
#             )
#             if not signature:
#                 logger.warning('Missing webhook signature header')
#                 return Response({'detail': 'Missing signature'}, status=400)
#             try:
#                 body = request.body or b''
#                 # provider may send "sha256=<hex>" or raw hex
#                 computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
#                 sig = signature
#                 if isinstance(sig, bytes):
#                     sig = sig.decode()
#                 if sig.startswith('sha256='):
#                     sig = sig.split('=', 1)[1]
#                 if not hmac.compare_digest(computed, sig):
#                     logger.warning('Invalid webhook signature: expected %s got %s', computed, sig)
#                     return Response({'detail': 'Invalid signature'}, status=403)
#             except Exception as e:
#                 logger.exception('Error verifying webhook signature: %s', e)
#                 return Response({'detail': 'Signature verification error'}, status=400)
#             print("WEBHOOK RECEIVED =>", request.data)
#         # Attempt to match by external_reference or transaction_id
#         payload = request.data
#         external_ref = payload.get('external_reference') or payload.get('reference')
#         tx_id = payload.get('transactionId') or payload.get('transaction_id') or payload.get('tx_id')
#         payment = None
#         if external_ref:
#             payment = Payment.objects.filter(order__external_reference=external_ref).first()
#         if not payment and tx_id:
#             payment = Payment.objects.filter(transaction_id=tx_id).first()

#         # Record webhook raw response
#         if payment:
#             payment.raw_response = payload
#             status_str = payload.get('status') or payload.get('payment_status') or payload.get('transactionStatus') or ''
#             if status_str and status_str.lower() in ('success','successful', 'completed', 'paid'):
#                 payment.status = Payment.STATUS_SUCCESS
#                 payment.save()
#                 order = payment.order
#                 order.status = Order.STATUS_PAID
#                 order.save()
#             else:
#                 payment.status = Payment.STATUS_FAILED
#                 payment.save()
#                 order = payment.order
#                 order.status = Order.STATUS_FAILED
#                 order.save()
#             return Response({'ok': True})

#         # If no payment matched, log and return 404
#         logger.warning('Webhook received for unknown payment: %s', payload)
#         return Response({'detail': 'Payment not found'}, status=404)


class PaymentStatusAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):

        order = get_object_or_404(
            Order,
            id=order_id,
            user=request.user
        )

        payment = Payment.objects.filter(order=order).first()

        if not payment:
            return Response({
                "success": False,
                "status": "FAILED",
                "message": "Payment not found"
            })

        # SUCCESS
        if order.status == Order.STATUS_PAID:
            return Response({
                "success": True,
                "status": "SUCCESS",
                "transaction_id": payment.provider_transaction_id,
                "message": "Payment successful"
            })

        # FAILED
        if order.status == Order.STATUS_FAILED:
            return Response({
                "success": False,
                "status": "FAILED",
                "transaction_id": payment.provider_transaction_id,
                "message": "Payment failed"
            })

        # PROCESSING
        return Response({
            "success": False,
            "status": "PROCESSING",
            "transaction_id": payment.provider_transaction_id,
            "message": "Waiting for payment confirmation"
        })
# class PaymentStatusAPIView(APIView):

#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request, order_id):

#         order = get_object_or_404(
#             Order,
#             id=order_id,
#             user=request.user
#         )

#         payment = (
#             Payment.objects
#             .filter(order=order)
#             .first()
#         )

#         if not payment:

#             return Response({
#                 "success": False,
#                 "status": "FAILED",
#                 "message": "Payment not found"
#             })

#         # already completed
#         if payment.status == Payment.STATUS_SUCCESS:

#             return Response({
#                 "success": True,
#                 "status": "SUCCESS",
#                 "transaction_id": payment.transaction_id,
#                 "message": "Payment successful"
#             })

#         # verify from provider
#         try:

#             client = AzamPayClient()

#             provider_resp = (
#                 client.get_transaction_status(
#                     payment.transaction_id
#                 )
#             )

#             print("PROVIDER VERIFY =>", provider_resp)

#             provider_status = (
#                 provider_resp
#                 .get("data", {})
#                 .get("transactionStatus", "")
#                 .upper()
#             )

#             payment.raw_response = provider_resp

#             if provider_status in [
#                 "SUCCESS",
#                 "COMPLETED",
#                 "PAID"
#             ]:

#                 payment.status = (
#                     Payment.STATUS_SUCCESS
#                 )

#                 order.status = (
#                     Order.STATUS_PAID
#                 )

#                 payment.save()

#                 order.save()

#                 return Response({
#                     "success": True,
#                     "status": "SUCCESS",
#                     "transaction_id":
#                         payment.transaction_id,
#                     "message":
#                         "Payment successful"
#                 })

#             elif provider_status in [
#                 "FAILED",
#                 "ERROR"
#             ]:

#                 payment.status = (
#                     Payment.STATUS_FAILED
#                 )

#                 order.status = (
#                     Order.STATUS_FAILED
#                 )

#                 payment.save()

#                 order.save()

#                 return Response({
#                     "success": False,
#                     "status": "FAILED",
#                     "transaction_id":
#                         payment.transaction_id,
#                     "message":
#                         "Payment failed"
#                 })

#             return Response({
#                 "success": False,
#                 "status": "PROCESSING",
#                 "transaction_id":
#                     payment.transaction_id,
#                 "message":
#                     "Payment still processing"
#             })

#         except Exception as e:

#             print("VERIFY ERROR =>", str(e))

#             return Response({
#                 "success": False,
#                 "status": "PROCESSING",
#                 "transaction_id":
#                     payment.transaction_id,
#                 "message":
#                     "Unable to verify yet"
#             })

# class PaymentStatusAPIView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request, order_id):
#         order = get_object_or_404(Order, id=order_id, user=request.user)
#         serializer = OrderStatusSerializer(order)
#         return Response(serializer.data)


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


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

        total = 0
        order = Order.objects.create(user=user, total_amount=0)
        for it in items:
            sid = it.get('service_id')
            qty = int(it.get('quantity', 1))
            try:
                svc = Service.objects.get(pk=sid, is_active=True)
            except Service.DoesNotExist:
                order.delete()
                return Response({'detail': f'Service {sid} not found'}, status=400)
            price = svc.price
            OrderItem.objects.create(order=order, service=svc, quantity=qty, price=price)
            total += float(price) * qty

        order.total_amount = total
        # assign representative if provided
        rep_id = request.data.get('representative_id')
        if rep_id:
            try:
                rep = Representative.objects.get(pk=int(rep_id), is_active=True)
                order.representative = rep
            except Exception:
                # ignore invalid representative
                pass
        order.save()
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        # simulate payment
        order.status = Order.STATUS_PAID
        order.save()
        return Response({'detail': 'Payment succeeded', 'status': order.status})


@api_view(['POST'])
def register_view(request):
    # expected: email, full_name, password
    email = request.data.get('email')
    full_name = request.data.get('full_name')
    password = request.data.get('password')
    if not email or not password or not full_name:
        return Response({'detail': 'email, full_name and password required'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=email).exists():
        return Response({'detail': 'User already exists'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=email, email=email, password=password)
    # split full_name into first/last
    parts = full_name.strip().split(' ', 1)
    user.first_name = parts[0]
    if len(parts) > 1:
        user.last_name = parts[1]
    user.save()
    # create JWT tokens for newly registered user
    refresh = RefreshToken.for_user(user)
    user_data = {
        'id': user.id,
        'name': f"{user.first_name} {user.last_name}".strip() or user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }
    return Response({'access': str(refresh.access_token), 'refresh': str(refresh), 'user': user_data})



class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user'] = {
            'id': user.id,
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'email': user.email,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        }
        return data


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


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
            'profile': profile_data,
        }
        return Response(data)

    if request.method == 'PUT':
        # accept form-data or json; update user and profile
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if email is not None:
            user.email = email
            user.username = email
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
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
            'profile': ProfileSerializer(profile).data,
        }
        return Response(data)

    if request.method == 'DELETE':
        # delete the user account
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)




@api_view(['GET'])
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

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
