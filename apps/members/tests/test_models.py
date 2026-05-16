"""Tests for the Member model — focused on the membership_id generator,
which fixes a real v1 bug (count()+1 collisions after deletes).
"""
import pytest

from apps.members.models import Member

pytestmark = pytest.mark.django_db


def _make(tsc, **kw):
    return Member.objects.create(
        tsc_number=tsc,
        first_name=kw.pop('first_name', 'Test'),
        last_name=kw.pop('last_name', 'Member'),
        **kw,
    )


class TestMembershipId:
    def test_first_member_gets_m00001(self):
        m = _make('TSC-1')
        assert m.membership_id == 'M00001'

    def test_ids_increment(self):
        a = _make('TSC-1')
        b = _make('TSC-2')
        assert a.membership_id == 'M00001'
        assert b.membership_id == 'M00002'

    def test_delete_does_not_cause_reuse(self):
        """The v1 bug: count()+1 reuses a number after a delete, then the
        unique constraint blows up. The max-suffix approach must skip the
        deleted number instead.
        """
        a = _make('TSC-1')   # M00001
        b = _make('TSC-2')   # M00002
        b.delete()
        c = _make('TSC-3')   # must be M00003, NOT M00002
        assert a.membership_id == 'M00001'
        assert c.membership_id == 'M00003'

    def test_delete_all_then_create_does_not_reuse(self):
        a = _make('TSC-1')   # M00001
        a.delete()
        b = _make('TSC-2')
        # Durable counter: the number is retired forever even with no
        # surviving rows. b must NOT be M00001.
        assert b.membership_id == 'M00002'

    def test_explicit_membership_id_is_preserved(self):
        m = Member(tsc_number='TSC-9', first_name='A', last_name='B')
        m.membership_id = 'M99999'
        m.save()
        assert Member.objects.get(pk=m.pk).membership_id == 'M99999'


class TestMemberHelpers:
    def test_full_name(self):
        m = _make('TSC-1', first_name='Grace', last_name='Mwangi')
        assert m.full_name == 'Grace Mwangi'

    def test_active_queryset(self):
        _make('TSC-1')
        inactive = _make('TSC-2')
        inactive.is_active = False
        inactive.save()
        assert Member.objects.active().count() == 1

    def test_with_account_queryset(self, django_user_model):
        m1 = _make('TSC-1')
        m2 = _make('TSC-2')
        u = django_user_model.objects.create_user(
            email='linked@example.com', password='StrongPass-12345',
        )
        m2.user = u
        m2.save()
        ids = set(Member.objects.with_account().values_list('pk', flat=True))
        assert ids == {m2.pk}
        assert m1.pk not in ids
