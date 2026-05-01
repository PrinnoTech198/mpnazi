import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class AzamPayClient:

    def __init__(self):

        self.auth_base_url = settings.AZAMPAY_AUTH_BASE_URL.rstrip("/")

        self.api_base_url = settings.AZAMPAY_API_BASE_URL.rstrip("/")

        self.client_id = settings.AZAMPAY_CLIENT_ID

        self.client_secret = settings.AZAMPAY_CLIENT_SECRET

        self.app_name = settings.AZAMPAY_APP_NAME

        self.callback_url = settings.AZAMPAY_CALLBACK_URL

    def _token(self):

        url = (
            f"{self.auth_base_url}/AppRegistration/GenerateToken"
        )

        payload = {
            "appName": self.app_name,
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        }

        response = requests.post(
            url,
            json=payload,
            timeout=60
        )

        print(response.status_code)
        print(response.text)

        response.raise_for_status()

        data = response.json()

        access_token = data["data"]["accessToken"]

        return access_token

    def _headers(self):

        token = self._token()

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def initiate_mobile_money(
        self,
        amount,
        phone_number,
        external_reference
    ):

        url = (
            f"{self.api_base_url}/azampay/mno/checkout"
        )

        payload = {
            "accountNumber": phone_number,
            "additionalProperties": {
                "property1": "value1",
                "property2": "value2"
            },
            "amount": str(amount),
            "currency": "TZS",
            "externalId": external_reference,
            "provider": "Mpesa",
            "callbackUrl": self.callback_url,
        }

        response = requests.post(
            url,
            json=payload,
            headers=self._headers(),
            timeout=60
        )

        print(response.status_code)
        print(response.text)

        response.raise_for_status()

        return response.json()
    
    def get_transaction_status(self, transaction_id):
        # url = (
        #     f"{self.api_base_url}/azampay/transaction/check-status"
        # )

        payload = {
            "pgTransactionId": transaction_id
        }

        response = requests.post(
            #url,
            json=payload,
            headers=self._headers(),
            timeout=60
        )

        print("VERIFY STATUS:", response.status_code)
        print("VERIFY BODY:", response.text)

        response.raise_for_status()

        return response.json()
    
    # def get_transaction_status(
    #     self,
    #     transaction_id
    # ):

    #     url = (
    #         f"{self.api_base_url}/azampay/transactionstatus/{transaction_id}"
    #     )

    #     response = requests.get(
    #         url,
    #         headers=self._headers(),
    #         timeout=15
    #     )

    #     response.raise_for_status()

    #     return response.json()



# import time
# import requests
# import logging
# from django.conf import settings
# from django.core.cache import cache

# logger = logging.getLogger(__name__)

# TOKEN_CACHE_KEY = 'azampay_access_token'


# class AzamPayClient:
#     def __init__(self):
#         # Use empty string defaults to avoid NoneType errors when env vars are missing
#         raw_base = (getattr(settings, 'AZAMPAY_BASE_URL', None) or '').strip()
#         # If a scheme is missing, default to https:// to avoid MissingSchema errors
#         if raw_base and not raw_base.startswith(('http://', 'https://')):
#             raw_base = 'https://' + raw_base
#         self.base_url = raw_base.rstrip('/')
#         self.client_id = (getattr(settings, 'AZAMPAY_CLIENT_ID', None) or '')
#         self.client_secret = (getattr(settings, 'AZAMPAY_CLIENT_SECRET', None) or '')
#         self.app_name = (getattr(settings, 'AZAMPAY_APP_NAME', None) or '')
#         self.callback_url = (getattr(settings, 'AZAMPAY_CALLBACK_URL', None) or '')
#         # Try to import an official AzamPay SDK if installed. We support a liberal
#         # set of possible module names and fall back to the HTTP client above.
#         self.sdk = None
#         try:
#             # common SDK module names: azampay, azampay_sdk, azampay_sdk_anga
#             for mod in ('azampay', 'azampay_sdk', 'azampay_sdk_anga'):
#                 try:
#                     self._sdk_module = __import__(mod)
#                     self.sdk = self._sdk_module
#                     break
#                 except Exception:
#                     self._sdk_module = None
#                     continue
#             # If SDK exposes a client class, attempt to instantiate it (best-effort)
#             if self.sdk is not None and hasattr(self.sdk, 'AzamPay'):
#                 try:
#                     # many SDKs accept client_id/client_secret/base_url or similar
#                     self.sdk_client = self.sdk.AzamPay(
#                         client_id=self.client_id,
#                         client_secret=self.client_secret,
#                         base_url=self.base_url,
#                     )
#                 except Exception:
#                     # fallback to module-level functions if any
#                     self.sdk_client = None
#             else:
#                 self.sdk_client = None
#         except Exception:
#             self.sdk = None
#             self._sdk_module = None
#             self.sdk_client = None

#     def _token(self):
#         cached = cache.get(TOKEN_CACHE_KEY)
#         if cached and cached.get('expires_at', 0) > time.time():
#             return cached['access_token']

#         if not self.base_url:
#             raise RuntimeError('AZAMPAY_BASE_URL is not configured. Set AZAMPAY_BASE_URL in settings to the AzamPay base URL (e.g. https://sandbox.azampay.tz)')
#         # Try several common token endpoint paths in case the provider uses a different path
#         candidates = [
#             f"{self.base_url}/oauth/token/",
#             f"{self.base_url}/oauth2/token/",
#             f"{self.base_url}/oauth/token",
#             f"{self.base_url}/oauth2/token",
#             f"{self.base_url}/api/oauth/token",
#             f"{self.base_url}/api/oauth2/token",
#         ]

#         payload = {
#             'grant_type': 'client_credentials',
#             'client_id': self.client_id,
#             'client_secret': self.client_secret,
#         }

#         last_resp = None
#         for token_url in candidates:
#             try:
#                 logger.debug('Attempting AzamPay token URL: %s', token_url)
#                 r = requests.post(token_url, data=payload, timeout=10)
#                 last_resp = r
#                 if r.status_code == 404:
#                     logger.debug('Token endpoint not found at %s (404), trying next candidate', token_url)
#                     continue
#                 r.raise_for_status()
#                 data = r.json()
#                 access = data.get('access_token') or data.get('access')
#                 expires_in = data.get('expires_in', 300)
#                 cache.set(TOKEN_CACHE_KEY, {'access_token': access, 'expires_at': time.time() + int(expires_in) - 10}, timeout=int(expires_in))
#                 return access
#             except requests.exceptions.HTTPError as he:
#                 # Non-404 HTTP errors should be surfaced but we keep trying other candidates
#                 logger.warning('HTTP error from %s: %s - body: %s', token_url, he, getattr(last_resp, 'text', None))
#                 continue
#             except Exception as e:
#                 logger.exception('Error requesting token from %s: %s', token_url, e)
#                 continue

#         # If we reach here no token endpoint succeeded
#         details = None
#         if last_resp is not None:
#             try:
#                 details = last_resp.text
#             except Exception:
#                 details = '<unable to read response body>'

#         tried = ', '.join(candidates)
#         logger.error('Failed to obtain AzamPay token. Tried endpoints: %s; last_response_status=%s; body=%s', tried, getattr(last_resp, 'status_code', None), details)
#         raise RuntimeError(f'Failed to obtain AzamPay token. Tried endpoints: {tried}. Last status: {getattr(last_resp, "status_code", None)}. Body: {details}')

#     def _headers(self):
#         token = self._token()
#         return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

#     def initiate_mobile_money(self, amount, phone_number, external_reference):
#         # Prefer SDK call (if available), otherwise fall back to HTTP endpoint.
#         if self.sdk is not None:
#             try:
#                 # Try common SDK method names in a best-effort manner
#                 if hasattr(self.sdk_client, 'initiate_mobile_money') and self.sdk_client is not None:
#                     return self.sdk_client.initiate_mobile_money(amount=amount, phone=phone_number, reference=external_reference, callback_url=self.callback_url)
#                 if hasattr(self.sdk, 'initiate_mobile_money'):
#                     return self.sdk.initiate_mobile_money(amount=amount, phone=phone_number, reference=external_reference, callback_url=self.callback_url)
#             except Exception as e:
#                 logger.exception('AzamPay SDK mobile_money call failed, falling back to HTTP: %s', e)

#         # HTTP fallback
#         url = f"{self.base_url}/payments/mobile_money/"
#         payload = {
#             'amount': str(amount),
#             'phone_number': phone_number,
#             'external_reference': external_reference,
#             'callback_url': self.callback_url,
#             'description': f'Payment for {self.app_name} - {external_reference}'
#         }
#         r = requests.post(url, json=payload, headers=self._headers(), timeout=15)
#         r.raise_for_status()
#         return r.json()

#     def initiate_card(self, amount, external_reference, return_url=None):
#         # SDK preferred
#         if self.sdk is not None:
#             try:
#                 if hasattr(self.sdk_client, 'initiate_card') and self.sdk_client is not None:
#                     return self.sdk_client.initiate_card(amount=amount, reference=external_reference, return_url=return_url or self.callback_url)
#                 if hasattr(self.sdk, 'initiate_card'):
#                     return self.sdk.initiate_card(amount=amount, reference=external_reference, return_url=return_url or self.callback_url)
#             except Exception as e:
#                 logger.exception('AzamPay SDK card initiation failed, falling back to HTTP: %s', e)

#         url = f"{self.base_url}/payments/card/"
#         payload = {
#             'amount': str(amount),
#             'external_reference': external_reference,
#             'callback_url': self.callback_url,
#             'return_url': return_url or self.callback_url,
#             'description': f'Card payment for {self.app_name} - {external_reference}'
#         }
#         r = requests.post(url, json=payload, headers=self._headers(), timeout=15)
#         r.raise_for_status()
#         return r.json()

#     def get_transaction_status(self, transaction_id=None, external_reference=None):
#         # Try SDK first
#         if self.sdk is not None:
#             try:
#                 if hasattr(self.sdk_client, 'get_status') and self.sdk_client is not None:
#                     return self.sdk_client.get_status(transaction_id=transaction_id, reference=external_reference)
#                 if hasattr(self.sdk, 'get_transaction_status'):
#                     return self.sdk.get_transaction_status(transaction_id=transaction_id, reference=external_reference)
#             except Exception as e:
#                 logger.exception('AzamPay SDK status check failed, falling back to HTTP: %s', e)

#         url = f"{self.base_url}/payments/status/"
#         params = {}
#         if transaction_id:
#             params['transaction_id'] = transaction_id
#         if external_reference:
#             params['external_reference'] = external_reference
#         r = requests.get(url, params=params, headers=self._headers(), timeout=10)
#         r.raise_for_status()
#         return r.json()
