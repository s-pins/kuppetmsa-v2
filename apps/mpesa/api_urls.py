"""API routes for the mpesa app.

Webhook paths match the env defaults in .env.example
(MPESA_VALIDATION_URL / MPESA_CONFIRMATION_URL / MPESA_CALLBACK_URL):
they resolve under /api/v1/mpesa/.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.mpesa.views import (
    C2BConfirmationView,
    C2BValidationView,
    MpesaTransactionViewSet,
    StkCallbackView,
    StkPushView,
)

app_name = "mpesa"

router = DefaultRouter()
router.register("transactions", MpesaTransactionViewSet, basename="transaction")

urlpatterns = [
    # Safaricom-called webhooks (server-to-server, no auth).
    path("validate/", C2BValidationView.as_view(), name="validate"),
    path("confirm/", C2BConfirmationView.as_view(), name="confirm"),
    path("callback/", StkCallbackView.as_view(), name="callback"),
    # Member-initiated.
    path("stk-push/", StkPushView.as_view(), name="stk-push"),
    *router.urls,
]
