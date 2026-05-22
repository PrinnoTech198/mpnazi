from django.urls import path

from payments.views.callback_views import PesapalCallbackView
from payments.webhooks.ipn_views import PesapalIPNAPIView

urlpatterns = [
    path("ipn/", PesapalIPNAPIView.as_view(), name="payments-pesapal-ipn"),
    path("ipn", PesapalIPNAPIView.as_view(), name="payments-pesapal-ipn-noslash"),
    path("callback/", PesapalCallbackView.as_view(), name="payments-pesapal-callback"),
    path("callback", PesapalCallbackView.as_view(), name="payments-pesapal-callback-noslash"),
]
