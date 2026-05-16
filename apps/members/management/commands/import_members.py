"""Bulk-import members from a CSV file.

Usage:
    python manage.py import_members path/to/roster.csv
    python manage.py import_members roster.csv --dry-run

Expected columns (header row required, order-independent):
    tsc_number, first_name, last_name, phone, email, school,
    sub_county, ward, joined_on

membership_id is auto-generated — do NOT include it in the CSV.

Rows with a tsc_number that already exists are skipped (reported), not
overwritten — import is additive and safe to re-run.
"""
from __future__ import annotations

import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.members.models import Member, SubCounty

REQUIRED = {'tsc_number', 'first_name', 'last_name'}
KNOWN = REQUIRED | {
    'phone', 'email', 'school', 'sub_county', 'ward', 'joined_on',
}
_VALID_SUBCOUNTIES = {c.value for c in SubCounty}


class Command(BaseCommand):
    help = 'Bulk-import members from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate and report without writing anything.',
        )

    def handle(self, *args, **opts):
        path = opts['csv_path']
        dry = opts['dry_run']

        try:
            fh = open(path, newline='', encoding='utf-8-sig')
        except OSError as exc:
            raise CommandError(f'Cannot open {path}: {exc}') from exc

        with fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise CommandError('CSV appears to be empty.')
            headers = {h.strip() for h in reader.fieldnames}
            missing = REQUIRED - headers
            if missing:
                raise CommandError(
                    f'Missing required column(s): {", ".join(sorted(missing))}'
                )
            unknown = headers - KNOWN
            if unknown:
                self.stdout.write(
                    self.style.WARNING(
                        f'Ignoring unknown column(s): {", ".join(sorted(unknown))}'
                    )
                )

            created = skipped = errors = 0
            existing_tsc = set(
                Member.objects.values_list('tsc_number', flat=True)
            )

            rows = list(reader)

        for i, row in enumerate(rows, start=2):  # row 1 is the header
            row = {k.strip(): (v or '').strip() for k, v in row.items()}
            tsc = row.get('tsc_number', '')

            if not tsc or not row.get('first_name') or not row.get('last_name'):
                self.stdout.write(self.style.ERROR(
                    f'Row {i}: missing required value, skipped.'
                ))
                errors += 1
                continue

            if tsc in existing_tsc:
                self.stdout.write(
                    f'Row {i}: tsc_number {tsc} already exists, skipped.'
                )
                skipped += 1
                continue

            sub_county = row.get('sub_county', '').lower()
            if sub_county and sub_county not in _VALID_SUBCOUNTIES:
                self.stdout.write(self.style.WARNING(
                    f'Row {i}: unknown sub_county "{sub_county}", left blank.'
                ))
                sub_county = ''

            joined_on = None
            if row.get('joined_on'):
                try:
                    joined_on = datetime.strptime(
                        row['joined_on'], '%Y-%m-%d'
                    ).date()
                except ValueError:
                    self.stdout.write(self.style.WARNING(
                        f'Row {i}: bad joined_on "{row["joined_on"]}" '
                        f'(want YYYY-MM-DD), left blank.'
                    ))

            if dry:
                created += 1
                existing_tsc.add(tsc)
                continue

            try:
                with transaction.atomic():
                    Member.objects.create(
                        tsc_number=tsc,
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        phone=row.get('phone', ''),
                        email=row.get('email', ''),
                        school=row.get('school', ''),
                        sub_county=sub_county,
                        ward=row.get('ward', ''),
                        joined_on=joined_on,
                    )
                created += 1
                existing_tsc.add(tsc)
            except Exception as exc:  # noqa: BLE001 - report and continue
                self.stdout.write(self.style.ERROR(
                    f'Row {i}: failed ({exc}), skipped.'
                ))
                errors += 1

        verb = 'Would create' if dry else 'Created'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {created}, skipped {skipped} existing, {errors} errors.'
        ))
