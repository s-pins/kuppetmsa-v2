"""Discipline tests — the highest-stakes suite in the system.

Each class proves one security property from docs/permissions.md §5.8.
If any of these regress, sensitive member data is at risk, so the
coverage here is deliberately exhaustive and adversarial.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.constants import (
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_TREASURER,
)
from apps.discipline.models import (
    CaseOutcome,
    CaseStatus,
    DisciplinaryAction,
    DisciplinaryCase,
)
from apps.members.models import Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def subject_member():
    return Member.objects.create(tsc_number="TSC-1", first_name="Asha", last_name="Otieno")


@pytest.fixture
def make_user(django_user_model):
    n = {"i": 0}

    def _make(
        role=ROLE_MEMBER,
        *,
        committee=False,
        two_fa=True,
        recent=True,
    ):
        n["i"] += 1
        u = django_user_model.objects.create_user(
            email=f"{role}-{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
            discipline_committee_member=committee,
            is_2fa_enrolled=two_fa,
        )
        if recent:
            u.last_strong_auth_at = timezone.now()
            u.save(update_fields=["last_strong_auth_at"])
        return u

    return _make


@pytest.fixture
def case(subject_member, make_user):
    opener = make_user(ROLE_CHAIRPERSON)
    return DisciplinaryCase.objects.create(
        subject=subject_member,
        category="misconduct",
        summary="CONFIDENTIAL: alleged misappropriation of branch funds.",
        opened_by=opener,
    )


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


CASES = "/api/v1/discipline/cases/"
MY = "/api/v1/discipline/my-cases/"


class TestEncryptionAtRest:
    """The defining property: plaintext must never sit in the DB."""

    def test_summary_is_ciphertext_in_database(self, case):
        secret = "alleged misappropriation of branch funds"
        # Read the raw column straight from the DB, bypassing the ORM
        # decryption layer. Query without a UUID WHERE clause to stay
        # backend-agnostic (SQLite stores UUIDs dashless; Postgres
        # native) — there is exactly one row.
        with connection.cursor() as cur:
            cur.execute("SELECT summary FROM discipline_disciplinarycase")
            row = cur.fetchone()
        assert row is not None, "case row not found — test setup broken"
        raw = row[0]
        # Whatever the storage form (bytes/memoryview/str), the
        # plaintext must not be present.
        raw_str = bytes(raw).decode("latin-1") if isinstance(raw, (bytes, memoryview)) else str(raw)
        assert secret not in raw_str
        # But the ORM transparently decrypts for in-process use.
        case.refresh_from_db()
        assert secret in case.summary

    def test_action_notes_encrypted_at_rest(self, case, make_user):
        recorder = make_user(ROLE_CHAIRPERSON)
        secret = "witness statement: saw the transfer on 12 March"
        action = DisciplinaryAction.objects.create(
            case=case,
            action_type="evidence",
            notes=secret,
            recorded_by=recorder,
        )
        with connection.cursor() as cur:
            cur.execute("SELECT notes FROM discipline_disciplinaryaction")
            row = cur.fetchone()
        assert row is not None, "action row not found — test setup broken"
        raw = row[0]
        raw_str = bytes(raw).decode("latin-1") if isinstance(raw, (bytes, memoryview)) else str(raw)
        assert secret not in raw_str
        action.refresh_from_db()
        assert action.notes == secret


class TestExistenceNonDisclosure:
    """Unauthorised callers must get 404, never 401/403 — they must not
    be able to tell the discipline module even exists."""

    def test_anonymous_gets_404_not_401(self, case):
        resp = APIClient().get(CASES)
        assert resp.status_code == 404

    def test_plain_member_gets_404_not_403(self, case, make_user):
        resp = _client(make_user(ROLE_MEMBER)).get(CASES)
        assert resp.status_code == 404

    def test_officer_without_committee_flag_gets_404(self, case, make_user):
        # Treasurer: a senior officer, but NOT discipline committee.
        resp = _client(make_user(ROLE_TREASURER)).get(CASES)
        assert resp.status_code == 404

    def test_case_detail_404_for_unauthorised(self, case, make_user):
        # Even with a valid case id, a non-committee user cannot
        # confirm it exists.
        resp = _client(make_user(ROLE_MEMBER)).get(f"{CASES}{case.id}/")
        assert resp.status_code == 404


class TestCommitteeGate:
    """role+flag AND 2FA AND recent-auth — all required."""

    def test_committee_member_with_full_creds_allowed(self, case, make_user):
        u = make_user(ROLE_MEMBER, committee=True)
        resp = _client(u).get(CASES)
        assert resp.status_code == 200

    def test_chairperson_base_role_allowed(self, case, make_user):
        resp = _client(make_user(ROLE_CHAIRPERSON)).get(CASES)
        assert resp.status_code == 200

    def test_committee_without_2fa_gets_404(self, case, make_user):
        u = make_user(ROLE_CHAIRPERSON, two_fa=False)
        assert _client(u).get(CASES).status_code == 404

    def test_committee_with_stale_auth_gets_404(self, case, make_user):
        u = make_user(ROLE_CHAIRPERSON, recent=False)
        u.last_strong_auth_at = timezone.now() - timedelta(hours=2)
        u.save(update_fields=["last_strong_auth_at"])
        assert _client(u).get(CASES).status_code == 404


class TestSubjectRedaction:
    """A member may see THAT they have a case + status/outcome, but
    NEVER the summary or internal action notes."""

    def test_subject_sees_own_case_redacted(self, case, subject_member, django_user_model):
        user = django_user_model.objects.create_user(
            email="subject@example.com",
            password="StrongPass-12345",
            role=ROLE_MEMBER,
        )
        subject_member.user = user
        subject_member.save()

        resp = _client(user).get(MY)
        assert resp.status_code == 200
        row = resp.data["results"][0]
        # Present: existence + status fields.
        assert row["case_number"] == case.case_number
        assert row["status"] == "opened"
        # Absent: every sensitive field. Not blanked — absent.
        assert "summary" not in row
        assert "actions" not in row
        assert "opened_by" not in row
        body = str(resp.data)
        assert "misappropriation" not in body

    def test_subject_cannot_reach_committee_endpoint(self, case, subject_member, django_user_model):
        user = django_user_model.objects.create_user(
            email="subject2@example.com",
            password="StrongPass-12345",
            role=ROLE_MEMBER,
        )
        subject_member.user = user
        subject_member.save()
        # The full committee view must 404 for the subject too.
        assert _client(user).get(f"{CASES}{case.id}/").status_code == 404

    def test_member_without_profile_denied_my_cases(self, make_user):
        # Officer account, no member profile.
        resp = _client(make_user(ROLE_TREASURER)).get(MY)
        assert resp.status_code in (403, 404)


class TestStateMachine:
    def test_full_lifecycle(self, case):
        case.advance(CaseStatus.UNDER_INVESTIGATION)
        case.advance(CaseStatus.HEARING)
        case.decide(CaseOutcome.WARNING)
        assert case.status == CaseStatus.DECIDED
        assert case.outcome == CaseOutcome.WARNING
        case.close()
        assert case.status == CaseStatus.CLOSED

    def test_illegal_transition_rejected(self, case):
        with pytest.raises(ValidationError):
            case.advance(CaseStatus.HEARING)  # skipped investigation

    def test_cannot_decide_without_concrete_outcome(self, case):
        case.advance(CaseStatus.UNDER_INVESTIGATION)
        case.advance(CaseStatus.HEARING)
        with pytest.raises(ValidationError):
            case.decide(CaseOutcome.PENDING)

    def test_reopen_only_from_closed(self, case):
        with pytest.raises(ValidationError):
            case.reopen()
        case.close()
        case.reopen()
        assert case.status == CaseStatus.UNDER_INVESTIGATION

    def test_case_number_is_unsequential(self, subject_member, make_user):
        opener = make_user(ROLE_CHAIRPERSON)
        c1 = DisciplinaryCase.objects.create(
            subject=subject_member,
            category="ethics",
            summary="x",
            opened_by=opener,
        )
        c2 = DisciplinaryCase.objects.create(
            subject=subject_member,
            category="ethics",
            summary="y",
            opened_by=opener,
        )
        assert c1.case_number != c2.case_number
        assert c1.case_number.startswith("DC-")
        # No incrementing relationship.
        assert not (
            c1.case_number[3:].isdigit()
            and c2.case_number[3:].isdigit()
            and int(c2.case_number[3:], 16) - int(c1.case_number[3:], 16) == 1
        )


class TestAuditExcludesPlaintext:
    """The audit-log diff must never capture the encrypted content."""

    def test_audit_entry_has_no_plaintext_summary(self, case):
        from auditlog.models import LogEntry

        case.advance(CaseStatus.UNDER_INVESTIGATION)
        entries = LogEntry.objects.get_for_object(case)
        assert entries.exists()
        for e in entries:
            blob = str(e.changes)
            assert "misappropriation" not in blob


class TestCommitteeWorkflowAPI:
    def test_committee_creates_and_adds_action(self, make_user, subject_member):
        u = make_user(ROLE_CHAIRPERSON)
        created = _client(u).post(
            CASES,
            {
                "subject": subject_member.pk,
                "category": "financial",
                "summary": "Initial complaint filed.",
            },
            format="json",
        )
        assert created.status_code == 201
        cid = created.data["id"]
        added = _client(u).post(
            f"{CASES}{cid}/add-action/",
            {"action_type": "note", "notes": "Interviewed treasurer."},
            format="json",
        )
        assert added.status_code == 201
