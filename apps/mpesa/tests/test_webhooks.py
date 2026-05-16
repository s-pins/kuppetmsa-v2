"""Webhook and STK endpoint tests.

End-to-end over the API, all on the stub adapter — proving Phase 3's
core promise: complete flow, zero credentials.
"""

import pytest
from rest_framework.test import APIClient

from apps.core.constants import ROLE_MEMBER, ROLE_TREASURER
from apps.finances.models import BankAccount, FinancialContribution
from apps.members.models import Member
from apps.mpesa.models import MpesaTransaction, MpesaTxnStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return BankAccount.objects.create(name="Main", paybill="600100")


@pytest.fixture
def member():
    return Member.objects.create(tsc_number="TSC-1", first_name="Asha", last_name="Otieno")


@pytest.fixture
def make_user(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER):
        n["i"] += 1
        return django_user_model.objects.create_user(
            email=f"{role}-{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
        )

    return _make


VALIDATE = "/api/v1/mpesa/validate/"
CONFIRM = "/api/v1/mpesa/confirm/"
CALLBACK = "/api/v1/mpesa/callback/"
STK = "/api/v1/mpesa/stk-push/"
TXNS = "/api/v1/mpesa/transactions/"


def _c2b_body(ref, receipt="QGR7XK2P9L", amount="1200"):
    return {
        "TransID": receipt,
        "TransAmount": amount,
        "MSISDN": "254712345678",
        "BillRefNumber": ref,
        "TransTime": "20260516120000",
    }


class TestC2BWebhooks:
    def test_validation_accepts_anonymously(self):
        resp = APIClient().post(VALIDATE, {}, format="json")
        assert resp.status_code == 200
        assert resp.data["ResultCode"] == 0

    def test_confirmation_creates_matched_contribution(self, account, member):
        resp = APIClient().post(CONFIRM, _c2b_body(member.membership_id), format="json")
        assert resp.status_code == 200
        assert resp.data["ResultCode"] == 0  # Safaricom ack shape
        c = FinancialContribution.objects.get()
        assert c.member == member
        assert c.reconciled is True

    def test_confirmation_unknown_ref_still_acks_but_unmatched(self, account):
        resp = APIClient().post(CONFIRM, _c2b_body("M99999"), format="json")
        assert resp.status_code == 200  # never make Safaricom retry
        assert FinancialContribution.objects.count() == 0
        txn = MpesaTransaction.objects.get()
        assert txn.status == MpesaTxnStatus.UNMATCHED

    def test_garbage_payload_still_acks(self, account):
        resp = APIClient().post(CONFIRM, {"not": "valid"}, format="json")
        # We must not 500 — Safaricom would retry forever.
        assert resp.status_code == 200

    def test_duplicate_webhook_credits_once(self, account, member):
        body = _c2b_body(member.membership_id)
        APIClient().post(CONFIRM, body, format="json")
        APIClient().post(CONFIRM, body, format="json")  # retry
        assert FinancialContribution.objects.count() == 1


class TestStkCallback:
    def _stk_body(self, receipt="QSTK123", result_code=0):
        items = [
            {"Name": "Amount", "Value": 750},
            {"Name": "MpesaReceiptNumber", "Value": receipt},
            {"Name": "TransactionDate", "Value": 20260516120000},
            {"Name": "PhoneNumber", "Value": 254712345678},
        ]
        return {
            "Body": {
                "stkCallback": {
                    "ResultCode": result_code,
                    "CallbackMetadata": {"Item": items},
                }
            }
        }

    def test_successful_stk_callback_records_payment(self, account, member):
        body = self._stk_body()
        body["__account_reference__"] = member.membership_id
        resp = APIClient().post(CALLBACK, body, format="json")
        assert resp.status_code == 200
        c = FinancialContribution.objects.get()
        assert c.source == "mpesa_stk"

    def test_cancelled_stk_callback_records_nothing(self, account, member):
        resp = APIClient().post(CALLBACK, self._stk_body(result_code=1032), format="json")
        assert resp.status_code == 200
        assert FinancialContribution.objects.count() == 0


class TestStkPushInitiation:
    def test_unauthenticated_denied(self):
        resp = APIClient().post(
            STK,
            {"msisdn": "254712345678", "amount_kes": "500"},
            format="json",
        )
        assert resp.status_code == 401

    def test_member_without_profile_gets_400(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_MEMBER))
        resp = c.post(
            STK,
            {"msisdn": "254712345678", "amount_kes": "500"},
            format="json",
        )
        assert resp.status_code == 400

    def test_member_with_profile_gets_stub_response(self, make_user, member):
        user = make_user(ROLE_MEMBER)
        member.user = user
        member.save()
        c = APIClient()
        c.force_authenticate(user)
        resp = c.post(
            STK,
            {"msisdn": "254712345678", "amount_kes": "500"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["checkout_request_id"].startswith("ws_STUB_")

    def test_bad_msisdn_rejected(self, make_user, member):
        user = make_user(ROLE_MEMBER)
        member.user = user
        member.save()
        c = APIClient()
        c.force_authenticate(user)
        resp = c.post(
            STK,
            {"msisdn": "0712345678", "amount_kes": "500"},
            format="json",
        )
        assert resp.status_code == 400


class TestTransactionReviewQueue:
    def test_member_cannot_see_transactions(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_MEMBER))
        assert c.get(TXNS).status_code == 403

    def test_treasurer_sees_unmatched_queue(self, account, make_user):
        APIClient().post(CONFIRM, _c2b_body("M99999"), format="json")
        c = APIClient()
        c.force_authenticate(make_user(ROLE_TREASURER))
        resp = c.get(f"{TXNS}unmatched/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["status"] == "unmatched"
