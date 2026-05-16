"""Reconciliation logic — the part Safaricom hammers with retries.

Idempotency is the headline test: a confirmation webhook delivered twice
must credit the member exactly once.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.finances.models import BankAccount, FinancialContribution
from apps.members.models import Member
from apps.mpesa.models import MpesaTransaction, MpesaTxnKind, MpesaTxnStatus
from apps.mpesa.reconciliation import InboundPayment, reconcile_inbound

pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return BankAccount.objects.create(name="Main", paybill="600100")


@pytest.fixture
def member():
    return Member.objects.create(tsc_number="TSC-1", first_name="Asha", last_name="Otieno")


def _payment(ref, receipt="QGR7XK2P9L", amount="1200.00"):
    return InboundPayment(
        mpesa_receipt=receipt,
        account_reference=ref,
        msisdn="254712345678",
        amount_kes=Decimal(amount),
        paid_at=timezone.now(),
        kind=MpesaTxnKind.C2B,
        raw_payload={"TransID": receipt},
    )


class TestMatching:
    def test_matched_payment_creates_reconciled_contribution(self, account, member):
        res = reconcile_inbound(_payment(member.membership_id))
        assert res.status == MpesaTxnStatus.MATCHED
        c = FinancialContribution.objects.get()
        assert c.member == member
        assert c.reconciled is True
        assert c.amount_kes == Decimal("1200.00")
        assert c.mpesa_ref == "QGR7XK2P9L"
        assert res.transaction.contribution == c

    def test_msisdn_is_masked_never_stored_raw(self, account, member):
        reconcile_inbound(_payment(member.membership_id))
        txn = MpesaTransaction.objects.get()
        assert txn.msisdn == "2547****5678"
        assert "254712345678" not in txn.msisdn

    def test_unknown_reference_flagged_unmatched_no_contribution(self, account):
        res = reconcile_inbound(_payment("M99999"))
        assert res.status == MpesaTxnStatus.UNMATCHED
        assert FinancialContribution.objects.count() == 0
        assert "Needs treasurer review" in res.transaction.note

    def test_no_active_account_flags_unmatched(self, member):
        # No BankAccount fixture used here.
        res = reconcile_inbound(_payment(member.membership_id))
        assert res.status == MpesaTxnStatus.UNMATCHED
        assert "no active bank account" in res.transaction.note.lower()

    def test_membership_id_match_is_case_insensitive(self, account, member):
        res = reconcile_inbound(_payment(member.membership_id.lower()))
        assert res.status == MpesaTxnStatus.MATCHED


class TestIdempotency:
    def test_duplicate_receipt_credits_once(self, account, member):
        p1 = _payment(member.membership_id)
        first = reconcile_inbound(p1)
        assert first.created is True
        assert first.status == MpesaTxnStatus.MATCHED

        # Safaricom retries the SAME receipt.
        p2 = _payment(member.membership_id)
        second = reconcile_inbound(p2)
        assert second.created is False

        # Exactly one contribution, one transaction.
        assert FinancialContribution.objects.count() == 1
        assert MpesaTransaction.objects.count() == 1

    def test_retry_of_unprocessed_marked_duplicate(self, account, member):
        # Force a pre-existing RECEIVED row, then retry.
        MpesaTransaction.objects.create(
            kind=MpesaTxnKind.C2B,
            mpesa_receipt="DUPE123",
            account_reference=member.membership_id,
            msisdn="2547****5678",
            amount_kes=Decimal("100.00"),
            paid_at=timezone.now(),
            status=MpesaTxnStatus.RECEIVED,
        )
        res = reconcile_inbound(_payment(member.membership_id, receipt="DUPE123"))
        assert res.created is False
        assert res.status == MpesaTxnStatus.DUPLICATE
