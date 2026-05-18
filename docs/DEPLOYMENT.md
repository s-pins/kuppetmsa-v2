# KUPPET MSA — Deployment & Operations Runbook

This document is the single source of truth for deploying and operating
the KUPPET Mombasa management system on the skymesh.co.ke host under
`kuppetmombasa.co.ke`. It is written to be followed by a competent operator
who is *not* the original developer — that is deliberate (see
§7, Bus-factor).

---

## 1. What you are deploying

A Django 5.2 / DRF application, ~12k lines, 212 automated tests. Eleven
domain apps (auth, members, finances, M-Pesa, events, projects,
reports, member portal, welfare, discipline, communications, public
site). Production server: gunicorn behind nginx; static files served by
WhiteNoise; PostgreSQL database; M-Pesa via Safaricom Daraja.

---

## 2. Prerequisites on the skymesh host

Confirm these before starting. **These were unconfirmed during the
build — verify each on the actual box and fill in the blanks.**

| Item | Required | Value on this host |
|---|---|---|
| OS | Ubuntu 22.04+ | `________` |
| Python | 3.12+ | `________` |
| PostgreSQL | 14+ | `________` |
| Root / sudo access | yes | `________` |
| Outbound HTTPS to Safaricom | yes (for live M-Pesa) | `________` |
| SMTP relay for `noreply@kuppetmombasa.co.ke` | yes (email verification) | `________` |
| TLS certificate for `kuppetmombasa.co.ke` | yes | `________` |

If any cell is unknown, resolve it before go-live — several have no
workaround (e.g. no SMTP means no member can verify their email and
therefore no member can ever log in).

---

## 3. First deployment

```bash
# 1. Clone and enter
git clone https://github.com/s-pins/kuppetmsa.git
cd kuppetmsa

# 2. Python environment
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements/production.txt   # falls back to base if absent

# 3. Environment file — copy and fill EVERY value
cp .env.example .env
#    Edit .env. See §4 for the keys that must be unique and how to
#    generate them. Do NOT reuse the example placeholders.

# 4. Database
#    Create the Postgres DB and user, put credentials in .env, then:
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# 5. Bootstrap (idempotent — safe to re-run)
python manage.py bootstrap \
    --admin-email it.admin@kuppetmombasa.co.ke \
    --admin-password '<strong value from the branch password manager>' \
    --bank-name 'KUPPET Mombasa Main Account' \
    --paybill <branch paybill, or omit until registered>

# 6. Pre-go-live audit — MUST exit 0 before opening to officers
python manage.py check_deploy

# 7. Run under gunicorn (process-manage with systemd; see §6)
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

`check_deploy` (step 6) is a hard gate. It exits non-zero and refuses
to pass if DEBUG is on, the encryption key is missing or equal to
SECRET_KEY, there is no active bank account, no admin exists, or
ALLOWED_HOSTS is empty. Do not open the system to users until it
exits 0.

---

## 4. Secrets — the critical part

`.env` contains 31 keys. Three are security-critical and must each be a
**distinct**, long, random value (generate with
`python -c "import secrets; print(secrets.token_urlsafe(64))"`):

| Key | Purpose | Rotation policy |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django session/CSRF signing | Routine rotation OK |
| `DJANGO_JWT_SIGNING_KEY` | API token signing | Rotation logs everyone out; otherwise safe |
| `DJANGO_FIELD_ENCRYPTION_KEY` | **Encrypts disciplinary records** | **NEVER rotate without a re-encryption migration** |

### 4.1 The encryption key — read this twice

`DJANGO_FIELD_ENCRYPTION_KEY` encrypts the `summary` and action `notes`
of every disciplinary case at rest. It is deliberately separate from
`DJANGO_SECRET_KEY` so that routine SECRET_KEY rotation does not touch
it.

**If this key is lost or changed, every existing disciplinary record
becomes permanently unreadable. There is no recovery.**

Therefore, before go-live:

1. Generate it once.
2. Store it in the branch password manager **and** on an offline
   backup (printed copy in the branch safe is acceptable and
   recommended).
3. Record, in writing, who holds the backup.
4. Never put it in git, in a ticket, in email, or in a chat message.
5. If it must ever change, that is a planned maintenance task
   requiring a data-migration that decrypts with the old key and
   re-encrypts with the new one — not an env edit.

`check_deploy` will FAIL if this key equals `DJANGO_SECRET_KEY`,
because that configuration would make a routine SECRET_KEY rotation
silently destroy all disciplinary data.

---

## 5. Policy thresholds requiring chairperson sign-off

Two financial thresholds are currently **placeholder values** in
`apps/core/constants.py`. They are functionally correct but the
*numbers* were assumed during the build, not supplied by the branch:

| Constant | Current value | Meaning |
|---|---|---|
| `LARGE_EXPENSE_THRESHOLD_KES` | 50,000 | Above this an expense needs a second leadership signatory (two-person rule) |
| `WELFARE_AUTO_APPROVE_THRESHOLD_KES` | 20,000 | At/below this a welfare officer may approve; above it needs leadership |

Before go-live the chairperson must confirm both against the branch's
actual financial and welfare regulations. `check_deploy` prints both
values as an INFO line specifically so this confirmation is not
forgotten.

**Changing a threshold after live data exists requires a code change +
migration + redeploy** — it is not a runtime setting. Get the numbers
right before the first real expense or claim is entered.

---

## 6. Process management (systemd sketch)

A minimal unit (adapt paths/user to the host):

```ini
[Unit]
Description=KUPPET MSA gunicorn
After=network.target postgresql.service

[Service]
User=kuppetmsa
WorkingDirectory=/srv/kuppetmsa
EnvironmentFile=/srv/kuppetmsa/.env
ExecStart=/srv/kuppetmsa/.venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

nginx terminates TLS for `kuppetmombasa.co.ke` and proxies to
`127.0.0.1:8000`. The M-Pesa webhook paths
(`/api/v1/mpesa/validate/`, `/confirm/`, `/callback/`) should
additionally be IP-allowlisted to Safaricom at the nginx layer — the
application already tolerates and de-duplicates retries, but
network-level restriction is defence in depth.

---

## 7. Bus-factor — operating this without the original developer

This was flagged as a real risk throughout the build. Mitigations now
in place:

- **This runbook** plus `docs/PLAN.md`, `docs/erd.md`,
  `docs/permissions.md` (the binding RBAC matrix).
- **`check_deploy`** encodes the non-obvious operational invariants as
  an automated audit, so an operator does not need to *remember* them.
- **212 automated tests + CI** — any change that breaks a documented
  behaviour fails before deploy.
- **Idempotent `bootstrap`** — safe to re-run; no special knowledge
  needed for first setup.

What is still a single point of failure and needs a human decision:

- There is no second developer. The branch should identify and brief
  at least one backup person who can at minimum: pull from GitHub,
  read `check_deploy` output, restore the database and the encryption
  key from backup, and restart the service.
- The encryption-key backup (4.1) is the highest-consequence single
  artifact. Its loss is unrecoverable; treat its custody like the
  branch's financial seals.

---

## 8. Routine operations

| Task | Command / action |
|---|---|
| Deploy an update | `git pull`, `pip install -r requirements/production.txt`, `migrate`, `collectstatic`, restart service, run `check_deploy` |
| Add an officer | Log in to `/admin/` as the admin account; create the user with the correct role (see `docs/permissions.md`) |
| Bulk-import members | `python manage.py import_members roster.csv` (supports `--dry-run`) |
| Investigate an unmatched M-Pesa payment | Treasurer reviews `/api/v1/mpesa/transactions/unmatched/` |
| Database backup | Nightly `pg_dump`; store off-host. Verify a restore at least once before relying on it. |
| Confirm deploy health | `python manage.py check_deploy` |

---

## 9. Go-live checklist

Do not announce the system to members until every box is checked.

- [ ] All §2 prerequisites confirmed on the skymesh host
- [ ] `.env` complete; the three security keys are distinct and random
- [ ] `DJANGO_FIELD_ENCRYPTION_KEY` backed up offline; custodian recorded
- [ ] `DJANGO_DEBUG=False` in the production environment
- [ ] `migrate` and `collectstatic` run cleanly
- [ ] `bootstrap` run; admin account access confirmed
- [ ] Real officer accounts created with correct roles
- [ ] Branch Paybill registered **to KUPPET Mombasa, not an officer
      personally**, and set on the active bank account
- [ ] `LARGE_EXPENSE_THRESHOLD_KES` confirmed by chairperson
- [ ] `WELFARE_AUTO_APPROVE_THRESHOLD_KES` confirmed by chairperson
- [ ] SMTP verified — a test signup receives its verification email
- [ ] `python manage.py check_deploy` exits 0
- [ ] Database backup job scheduled and a test restore performed
- [ ] At least one backup operator briefed (§7)
- [ ] Manual smoke test on the deployed box: member signup →
      verify email → log in → view portal; officer logs an expense;
      treasurer sees it; public transparency page loads
