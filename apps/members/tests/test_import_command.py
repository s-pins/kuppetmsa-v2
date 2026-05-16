"""Tests for the import_members management command."""

import io

import pytest
from django.core.management import call_command

from apps.members.models import Member

pytestmark = pytest.mark.django_db


def _run(csv_text, *args):
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".csv",
        delete=False,
        encoding="utf-8",
    ) as fh:
        fh.write(csv_text)
        path = fh.name
    out = io.StringIO()
    call_command("import_members", path, *args, stdout=out)
    return out.getvalue()


GOOD = (
    "tsc_number,first_name,last_name,school,sub_county,joined_on\n"
    "TSC-1,Grace,Mwangi,Coast High,mvita,2020-01-15\n"
    "TSC-2,John,Otieno,Bay Primary,nyali,2019-09-01\n"
)


class TestImportMembers:
    def test_imports_valid_rows(self):
        out = _run(GOOD)
        assert Member.objects.count() == 2
        assert "Created 2" in out
        m = Member.objects.get(tsc_number="TSC-1")
        assert m.first_name == "Grace"
        assert m.sub_county == "mvita"
        assert str(m.joined_on) == "2020-01-15"
        assert m.membership_id == "M00001"

    def test_dry_run_writes_nothing(self):
        out = _run(GOOD, "--dry-run")
        assert Member.objects.count() == 0
        assert "Would create 2" in out

    def test_existing_tsc_skipped_not_overwritten(self):
        Member.objects.create(
            tsc_number="TSC-1",
            first_name="Original",
            last_name="Name",
        )
        out = _run(GOOD)
        assert Member.objects.count() == 2  # only TSC-2 added
        assert Member.objects.get(tsc_number="TSC-1").first_name == "Original"
        assert "skipped 1 existing" in out

    def test_missing_required_column_aborts(self):
        bad = "first_name,last_name\nA,B\n"
        with pytest.raises(Exception) as exc:
            _run(bad)
        assert "tsc_number" in str(exc.value)

    def test_bad_row_skipped_others_continue(self):
        mixed = (
            "tsc_number,first_name,last_name\n"
            "TSC-1,Grace,Mwangi\n"
            ",Missing,Tsc\n"  # no tsc -> error row
            "TSC-3,Jane,Doe\n"
        )
        out = _run(mixed)
        assert Member.objects.count() == 2
        assert "1 errors" in out

    def test_unknown_sub_county_blanked(self):
        csv_text = "tsc_number,first_name,last_name,sub_county\nTSC-1,Grace,Mwangi,atlantis\n"
        _run(csv_text)
        assert Member.objects.get(tsc_number="TSC-1").sub_county == ""
