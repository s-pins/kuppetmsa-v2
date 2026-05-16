# KUPPET MSA — Mombasa County KUPPET management system

Django + DRF backend for the Mombasa County branch of KUPPET (Kenya Union of
Post Primary Education Teachers).

**Production domain:** kuppetmsa.co.ke
**Hosting:** skymesh.co.ke cloud

---

## Project status

**Phase 0 — Foundation complete.** This repo currently ships:

- Django 5.2 project with split settings (development / production)
- Custom email-login `User` model with role + capability flags
- `apps/core/constants.py` — single source of truth for roles and groups
- `apps/core/permissions.py` — DRF permission classes built from constants
- `apps/core/mixins.py` — same checks for server-rendered views
- `apps/core/schema.py` — drf-spectacular hook that strips discipline endpoints from the schema for unauthorized callers
- JWT auth via `djangorestframework-simplejwt` with blacklist on logout
- OpenAPI schema + Swagger UI + Redoc, **all gated to officer roles**
- CI: ruff lint + format check, pytest with coverage
- Tests for every permission class and the JWT/Swagger flow

The next phases are tracked in `docs/PLAN.md`. The permissions matrix that
drives `core/constants.py` is in `docs/permissions.md` — read that before
modifying any auth code.

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
  core/                  constants, permission classes, view mixins, schema hooks
  accounts/              custom User model, JWT views, /me endpoint
docs/
  PLAN.md                the v2 plan & sprint map
  permissions.md         the binding permissions matrix
  erd.md                 entity-relationship diagrams (3 sub-ERDs, mermaid)
requirements/
  base.txt               shared deps
  development.txt        dev-only (pytest, ruff, ipython)
  production.txt         prod-only (sentry)
templates/               server-rendered templates (populated in phase 1+)
```

## Key conventions

1. **Never write `if user.role == 'chairperson'`.** Import from `apps.core.constants` and use a group constant. If your check doesn't fit an existing group, add a group — don't inline.
2. **Default-deny on every API endpoint.** Every viewset starts `permission_classes = [IsAuthenticated, ...]`. Public endpoints opt out explicitly.
3. **404, not 403, for discipline.** The discipline module never confirms its own existence to unauthorized callers.
4. **Matrix wins.** If `docs/permissions.md` and the code disagree, the matrix is authoritative — the code gets fixed.
5. **No secrets in code.** Everything goes through `decouple.config(...)`.

## Phase 0 sign-off checklist

Before moving to phase 1:

- [ ] `pytest` passes locally
- [ ] `ruff check . && ruff format --check .` clean
- [ ] Can create a superuser
- [ ] Can obtain a JWT and call `/api/v1/accounts/me/`
- [ ] Member account is denied at `/api/v1/docs/` (gets 403)
- [ ] Officer account is admitted at `/api/v1/docs/`
- [ ] `docs/permissions.md` reviewed and signed off by the chairperson

## Phase 1 next steps

1. Wire `django-allauth` for member self-registration + email verification
2. Add the `accounts:reauth` view (referenced by `RecentAuthRequiredMixin`)
3. Add 2FA enrollment via `allauth.mfa`
4. Build the `members` app: Member model, CRUD viewsets, CSV import
5. Add the officer console skeleton (server-rendered with HTMX)

## License

Internal project; not licensed for redistribution.
