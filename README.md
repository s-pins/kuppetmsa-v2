# KUPPET MSA — Mombasa County KUPPET management system

Django + DRF backend for the Mombasa County branch of KUPPET (Kenya Union of
Post Primary Education Teachers).

**Production domain:** kuppetmsa.co.ke
**Hosting:** skymesh.co.ke cloud

---

## Project status

**Complete — all build phases (0–11) delivered.** This is the full
functional system, ~12.5k lines, 220 automated tests, CI-green.

What ships:

- **Foundation** — split settings, custom email-login `User` with
  role + capability flags, constants-driven RBAC, JWT auth,
  officer-gated OpenAPI.
- **Members & auth** — django-allauth signup/verification/2FA, the
  `members` app with race-safe membership IDs and CSV import.
- **Finances** — bank accounts, contributions, expenses with a
  model-enforced two-person rule, full audit trail, public
  transparency aggregates.
- **M-Pesa** — stub/live adapter (works credential-free until Daraja
  is wired), C2B + STK, idempotent reconciliation.
- **Events / projects / reports** — with budget-vs-actual flowing to
  the public site.
- **Member portal** — self-scoped dashboard, contributions, events.
- **Welfare** — claim state machine, threshold gate, finance
  integration on disbursement.
- **Discipline** — field-level encryption at rest, 404 existence
  non-disclosure, subject redaction (the most sensitive module).
- **Communications** — targeted announcements, idempotent fan-out,
  per-member inbox.
- **Public site** — leak-defended unauthenticated surface.
- **Operations** — idempotent `bootstrap`, the `check_deploy`
  go-live gate, and the full runbook.

### Before you deploy — read this first

**`docs/DEPLOYMENT.md` is the deployment & operations runbook.** It is
written for an operator who is not the original developer and contains
the skymesh setup, the encryption-key custody procedure, the
chairperson threshold sign-offs, and the go-live checklist. Do not
deploy from this README alone.

Three things require human decisions the code cannot make for you and
are called out in the runbook:

1. `DJANGO_FIELD_ENCRYPTION_KEY` must be generated, backed up offline,
   and never rotated without a re-encryption migration — losing it
   permanently destroys all disciplinary records.
2. `LARGE_EXPENSE_THRESHOLD_KES` and
   `WELFARE_AUTO_APPROVE_THRESHOLD_KES` are placeholder values until
   the chairperson confirms them against branch regulations.
3. The M-Pesa Paybill must be registered to KUPPET Mombasa, not to an
   officer personally.

`python manage.py check_deploy` audits the machine-checkable subset of
the above and exits non-zero until the deployment is ready.

## Quick start

```bash
git clone https://github.com/s-pins/kuppetmsa.git
cd kuppetmsa

python -m venv .venv
source .venv/bin/activate
pip install -r requirements/development.txt

cp .env.example .env
# edit .env — at minimum set DJANGO_SECRET_KEY

python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then:

- Admin: <http://localhost:8000/admin/>
- API root: <http://localhost:8000/api/v1/>
- Get a token: `POST /api/v1/auth/token/` with `{"email": "...", "password": "..."}`
- Try `/api/v1/accounts/me/` with `Authorization: Bearer <access>`
- Swagger (officer-only): <http://localhost:8000/api/v1/docs/>

## Running tests

```bash
pytest
```

## Layout

```
config/                  Django project (settings split, root URLconf, WSGI/ASGI)
  settings/
    base.py              shared
    development.py       SQLite, DEBUG=True
    production.py        Postgres, HTTPS, Sentry
  urls.py                root URLconf
  api_urls.py            /api/v1/* namespace
apps/
  core/                  constants, permissions, mixins, schema hooks, ops commands
  accounts/              custom User, JWT, allauth integration, 2FA
  members/               Member model, CSV import, officer console
  finances/              bank accounts, contributions, expenses, two-person rule
  mpesa/                 stub/live Daraja adapter, C2B/STK, reconciliation
  events/ projects/ reports/   activities + budget-vs-actual
  portal/                self-scoped member dashboard
  welfare/               claim state machine + finance integration
  discipline/            encrypted, 404-non-disclosure (most sensitive)
  communications/        targeted announcements + member inbox
  public_site/           leak-defended public surface
docs/
  PLAN.md                the v2 plan & sprint map
  permissions.md         the binding permissions matrix
  erd.md                 entity-relationship diagrams (mermaid)
  DEPLOYMENT.md          deployment & operations runbook — READ BEFORE DEPLOY
requirements/
  base.txt               shared deps
  development.txt        dev-only (pytest, ruff, ipython)
  production.txt         prod-only (sentry, psycopg)
```

Operational commands (see `docs/DEPLOYMENT.md`):

```bash
python manage.py bootstrap --admin-email ... --admin-password ...   # idempotent first-run
python manage.py check_deploy                                       # go-live gate
python manage.py import_members roster.csv [--dry-run]              # bulk member import
```

## Key conventions

1. **Never write `if user.role == 'chairperson'`.** Import from `apps.core.constants` and use a group constant. If your check doesn't fit an existing group, add a group — don't inline.
2. **Default-deny on every API endpoint.** Every viewset starts `permission_classes = [IsAuthenticated, ...]`. Public endpoints opt out explicitly.
3. **404, not 403, for discipline.** The discipline module never confirms its own existence to unauthorized callers.
4. **Matrix wins.** If `docs/permissions.md` and the code disagree, the matrix is authoritative — the code gets fixed.
5. **No secrets in code.** Everything goes through `decouple.config(...)`.

## For a new maintainer

Start here, in order:

1. `docs/PLAN.md` — what was built and why.
2. `docs/permissions.md` — the binding RBAC matrix. **If the code and
   this matrix disagree, the matrix is authoritative.**
3. `docs/erd.md` — the data model (3 mermaid sub-ERDs).
4. `docs/DEPLOYMENT.md` — how to run it on skymesh, and the
   bus-factor section specifically written for you.
5. Run `pytest` (expect ~220 passing) and
   `ruff check . && ruff format --check .` (clean) to confirm a sane
   working copy before changing anything.

The test suite is the safety net: every permission row in the matrix
has a test, and every phase of the build caught at least one real bug
through it. Trust a red test over your assumptions, and verify a
surprising green or red against ground truth before acting on it.

## License

Internal project; not licensed for redistribution.
