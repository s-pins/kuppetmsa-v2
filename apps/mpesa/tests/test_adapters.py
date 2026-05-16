"""Adapter selection and stub behaviour.

The defining Phase 3 property: with no credentials, everything works via
the stub and zero network calls happen.
"""

from decimal import Decimal

import pytest

from apps.mpesa.adapters import (
    DarajaMpesaAdapter,
    StubMpesaAdapter,
    get_adapter,
)
from apps.mpesa.config import MpesaSettings

pytestmark = pytest.mark.django_db


def _settings(**over):
    base = dict(
        consumer_key="",
        consumer_secret="",
        paybill="",
        passkey="",
        callback_url="https://x/cb/",
        validation_url="https://x/val/",
        confirmation_url="https://x/con/",
        environment="sandbox",
    )
    base.update(over)
    return MpesaSettings(**base)


class TestAdapterSelection:
    def test_no_credentials_yields_stub(self):
        s = _settings()
        assert s.has_credentials is False
        assert isinstance(get_adapter(s), StubMpesaAdapter)

    def test_full_credentials_yields_daraja(self):
        s = _settings(
            consumer_key="ck",
            consumer_secret="cs",
            paybill="600100",
            passkey="pk",
        )
        assert s.has_credentials is True
        assert isinstance(get_adapter(s), DarajaMpesaAdapter)

    def test_partial_credentials_still_stub(self):
        # Missing passkey -> not configured -> stub (fail safe).
        s = _settings(consumer_key="ck", consumer_secret="cs", paybill="600100")
        assert s.has_credentials is False
        assert isinstance(get_adapter(s), StubMpesaAdapter)

    def test_base_url_switches_on_environment(self):
        assert "sandbox" in _settings().base_api_url
        assert "sandbox" not in _settings(environment="production").base_api_url


class TestStubAdapter:
    def test_stub_stk_push_makes_no_network_call(self):
        adapter = StubMpesaAdapter(_settings())
        result = adapter.initiate_stk_push(
            msisdn="254712345678",
            amount=Decimal("500"),
            account_reference="M00001",
            description="dues",
        )
        assert result.ok is True
        assert result.checkout_request_id.startswith("ws_STUB_")
        assert "Stub mode" in result.customer_message

    def test_stub_c2b_registration_is_noop(self):
        adapter = StubMpesaAdapter(_settings())
        assert adapter.register_c2b_urls()["stub"] is True
