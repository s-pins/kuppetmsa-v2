"""M-Pesa adapters.

One interface, two implementations:

  StubMpesaAdapter   — no network. STK "push" just records intent to the
                       audit log and returns a synthetic CheckoutRequestID.
                       This is the DEFAULT whenever credentials are absent,
                       so every flow is testable without a merchant
                       account.

  DarajaMpesaAdapter — real Safaricom Daraja calls (OAuth token, STK push,
                       C2B URL registration). Selected automatically when
                       MpesaSettings.has_credentials is True.

get_adapter() is the only thing callers use; they never branch on
credentials themselves.
"""

from __future__ import annotations

import base64
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from apps.mpesa.config import MpesaSettings, load_settings

logger = logging.getLogger("mpesa")


@dataclass
class StkPushResult:
    ok: bool
    checkout_request_id: str
    customer_message: str
    raw: dict


class BaseMpesaAdapter(ABC):
    def __init__(self, settings: MpesaSettings):
        self.settings = settings

    @abstractmethod
    def initiate_stk_push(
        self, *, msisdn: str, amount, account_reference: str, description: str
    ) -> StkPushResult: ...

    @abstractmethod
    def register_c2b_urls(self) -> dict: ...


class StubMpesaAdapter(BaseMpesaAdapter):
    """No-network adapter. Used until live credentials are provided."""

    def initiate_stk_push(
        self, *, msisdn: str, amount, account_reference: str, description: str
    ) -> StkPushResult:
        synthetic_id = f"ws_STUB_{uuid.uuid4().hex[:16]}"
        logger.info(
            "STUB STK push: msisdn=%s amount=%s ref=%s desc=%s -> %s",
            MpesaTxn_mask(msisdn),
            amount,
            account_reference,
            description,
            synthetic_id,
        )
        return StkPushResult(
            ok=True,
            checkout_request_id=synthetic_id,
            customer_message=(
                "Stub mode: no real STK prompt sent. Configure Daraja "
                "credentials to enable live payments."
            ),
            raw={"stub": True},
        )

    def register_c2b_urls(self) -> dict:
        logger.info(
            "STUB C2B URL registration (no-op). validation=%s confirmation=%s",
            self.settings.validation_url,
            self.settings.confirmation_url,
        )
        return {"stub": True, "ResponseDescription": "stubbed"}


class DarajaMpesaAdapter(BaseMpesaAdapter):
    """Real Safaricom Daraja adapter.

    Network calls are isolated here so the rest of the system never
    imports requests. Only exercised when credentials are present.
    """

    def _oauth_token(self) -> str:
        import requests

        url = f"{self.settings.base_api_url}/oauth/v1/generate?grant_type=client_credentials"
        resp = requests.get(
            url,
            auth=(
                self.settings.consumer_key,
                self.settings.consumer_secret,
            ),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _password(self, timestamp: str) -> str:
        raw = (f"{self.settings.paybill}{self.settings.passkey}{timestamp}").encode()
        return base64.b64encode(raw).decode()

    def initiate_stk_push(
        self, *, msisdn: str, amount, account_reference: str, description: str
    ) -> StkPushResult:
        import requests

        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        token = self._oauth_token()
        payload = {
            "BusinessShortCode": self.settings.paybill,
            "Password": self._password(timestamp),
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": msisdn,
            "PartyB": self.settings.paybill,
            "PhoneNumber": msisdn,
            "CallBackURL": self.settings.callback_url,
            "AccountReference": account_reference[:12],
            "TransactionDesc": description[:13],
        }
        resp = requests.post(
            f"{self.settings.base_api_url}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        body = resp.json()
        ok = resp.status_code == 200 and body.get("ResponseCode") == "0"
        return StkPushResult(
            ok=ok,
            checkout_request_id=body.get("CheckoutRequestID", ""),
            customer_message=body.get("CustomerMessage", ""),
            raw=body,
        )

    def register_c2b_urls(self) -> dict:
        import requests

        token = self._oauth_token()
        payload = {
            "ShortCode": self.settings.paybill,
            "ResponseType": "Completed",
            "ConfirmationURL": self.settings.confirmation_url,
            "ValidationURL": self.settings.validation_url,
        }
        resp = requests.post(
            f"{self.settings.base_api_url}/mpesa/c2b/v1/registerurl",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        return resp.json()


def MpesaTxn_mask(raw: str) -> str:
    # Local import avoids a model import at module load.
    from apps.mpesa.models import MpesaTransaction

    return MpesaTransaction.mask_msisdn(raw)


def get_adapter(settings: MpesaSettings | None = None) -> BaseMpesaAdapter:
    """Single entry point. Stub unless real credentials exist."""
    settings = settings or load_settings()
    if settings.has_credentials:
        return DarajaMpesaAdapter(settings)
    return StubMpesaAdapter(settings)
