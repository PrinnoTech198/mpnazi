"""Browser return URL after Pesapal checkout (customer redirect only — not verification)."""
from django.http import HttpResponse
from django.views import View


class PesapalCallbackView(View):
    def get(self, request):
        tracking = request.GET.get("OrderTrackingId", "")
        ref = request.GET.get("OrderMerchantReference", "")
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Payment</title></head>
<body style="font-family:sans-serif;text-align:center;padding:2rem">
<h1>Payment received</h1>
<p>You may close this page and return to the Mpanzi app.</p>
<p style="color:#666;font-size:0.9rem">Reference: {ref}<br>Tracking: {tracking}</p>
</body></html>"""
        return HttpResponse(html, content_type="text/html")
