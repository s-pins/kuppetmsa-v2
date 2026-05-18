# KUPPET MSA v2 — Plan, Architecture & Sprint Map

**Project:** Mombasa County KUPPET management system
**Domain:** kuppetmombasa.co.ke (hosted on skymesh.co.ke cloud)
**Maintainer:** sole developer (self-funded; client compensation deferred)
**Document status:** v0.3 — DRF + JWT + Swagger added across all modules; ready for kickoff

---

## 1. Context & framing

The Mombasa County branch of KUPPET (Kenya Union of Post Primary Education Teachers) needs a management system that does three jobs at once:

1. **Public transparency.** Members, the press, and the wider teaching community can see how the branch is run — leadership, finances, projects, events, manifestos — without logging in. This is the union's accountability shop window.
2. **Member self-service.** Registered members can log in to see their own dues and contribution history, RSVP to events, update their profile, and receive announcements without phoning the office.
3. **Officer operations.** The chairperson, executive secretary, treasurer, organizing secretary, and sectoral secretaries can record contributions, manage expenses, log events, upload reports, and communicate with the membership — with every sensitive action audited.

The system is **not** an electoral platform. It hosts campaign information (candidates, manifestos, election schedules, video ads) but voting itself happens through the union's existing constitutional process.

The v1 prototype at `github.com/s-pins/kuppetmsa` is a useful sketch but has structural issues (role-name drift, mixed concerns, no audit trail, no Mpesa, no member portal). v2 is a clean rebuild that keeps the v1 domain model where it's solid (finances) and rewrites the rest.

## 2. Goals and explicit non-goals

**In scope for v2:**

- Public transparency site
- Member self-service portal with first-login onboarding tour
- Officer admin console with role-based access
- Financial accounting with full audit trail
- M-Pesa Daraja integration via branch-owned Paybill (code-ready; credentials swapped in via env when the chapter activates the merchant account)
- Welfare claims module
- Disciplinary records module (restricted access, encrypted)
- Broadcast email + in-system inbox
- Events, projects, reports, gallery, manifesto modules (manifesto with versioning)
- **Full REST API (DRF) across every module** with JWT authentication
- **OpenAPI/Swagger documentation gated to officers**
- Production deployment to kuppetmombasa.co.ke with backups, monitoring, HTTPS
- Officer training sessions + member tutorial pages

**Explicit non-goals for v2 (deferred to v2.1 or later):**

- Live online voting
- Mobile native apps (responsive web is the answer for now)
- SMS broadcasts (Africa's Talking integration is a one-week add-on later)
- Public-facing API for third parties
- Cross-county aggregation (this is a Mombasa-branch system, not a national KUPPET platform)
- Complex BI/reporting beyond the public transparency dashboard

## 3. Users and roles

Four user archetypes, mapped to the KUPPET branch constitution:

| Archetype | Auth | What they can do |
|---|---|---|
| **Public visitor** | Anonymous | Browse public pages: leaders, events, finances summary, gallery, manifesto, contacts |
| **Member** | Logged in | All public + view own profile, contribution history, RSVP to events, inbox |
| **Officer** | Logged in, role-gated | Member-level access + their role-specific officer functions |
| **Admin** | Logged in, superuser | All of the above + user management, system config |

**Officer roles** (mirroring the v1 ROLE_CHOICES, cleaned up):

- `chairperson`, `vice_chairperson`
- `executive_secretary`, `assistant_executive_secretary`
- `treasurer`, `assistant_treasurer`
- `organizing_secretary`
- `secretary_secondary` (note: fix v1 typo `secretay_secondary`), `secretary_tertiary`, `secretary_junior_school`, `secretary_gender`
- `gender_assistant_1st`, `gender_plwds_2nd`, `gender_youth_3rd`

These live in **one place** — `core/constants.py` — and every permission decorator references that module. No more drift between `accounts/models.py` and view decorators.

A permission matrix (who can do what) goes in `docs/permissions.md` and is reviewed with the chairperson before launch.

## 4. Functional scope by module

### `accounts` — identity & RBAC
- Custom `User` extending `AbstractUser`, email login
- Single-source role enum from `core.constants.ROLES`
- Signup with email verification (django-allauth)
- Password reset via email
- Optional 2FA (TOTP) — **required** for `treasurer`, `assistant_treasurer`, `executive_secretary`
- Last-login + login-IP tracking for security review

### `members` — member profiles
- Fields: first/last name, TSC number, ID number, phone, email, school, sub-county, ward, photo, bio, join date, active flag, slug
- One-to-one optional link to `User` (a member may or may not have an account)
- Officer-side CRUD; member-side self-edit on safe fields only (contact, photo, bio)
- Bulk import via CSV (officer-only, audited)
- Search + filter by school, ward, active status

### `public_site` — anonymous-facing pages
- Home: branch snapshot, leadership grid, upcoming events, transparency widget (totals)
- Leaders / executives page (with current role badges)
- Events: upcoming and past with photo album links
- Transparency: total contributions, total expenses, monthly breakdown, project spend (read-only, cached)
- Gallery: albums and media items
- Manifesto viewer (PDF embed)
- Elections info: candidates by position, election schedule, campaign video
- Contacts page with a contact form (rate-limited)

### `member_portal` — logged-in member area
- Dashboard: my contributions, my upcoming RSVPs, unread messages
- My profile: view & edit safe fields
- My contributions: paginated history with downloadable receipts (PDF)
- My events: RSVP and attendance log
- Inbox: messages from officers
- Notification preferences (email on/off per category)

### `officer_console` — admin tools
- Dashboard: counts, monthly contribution chart, recent activity, outstanding tasks
- Members admin: list, search, edit, deactivate, import, export
- Finances admin: record contribution, record expense, reconcile Mpesa, manage bank accounts
- Events admin: create/edit/delete, attendance marking, attach album
- Projects admin: CRUD, status updates, expense tagging
- Reports admin: upload (with file validation), categorize, publish/unpublish
- Communications: compose broadcast, target by role/school/sub-county, send
- Audit log viewer (read-only)

### `finances` — money tracking
- `BankAccount`, `FinancialContribution`, `Expense` (v1 design retained — it's solid)
- M-Pesa integration in a sub-app:
  - STK Push initiator (member triggers payment from portal)
  - C2B validation + confirmation webhooks (for Paybill/Till deposits made outside the system)
  - Reconciliation service (matches incoming Mpesa refs to contributions, flags unmatched for officer review)
- Budget per project (planned vs actual)
- Receipt PDF generation per contribution
- Public transparency aggregates cached with 5-minute TTL

### `events` — events & RSVP
- `Event` (title, date nullable, location, type, image, description)
- `EventAttendance` (m2m through with RSVP + attended flags)
- Officer-side: create, edit, mark attendance
- Member-side: RSVP, view own attendance history
- Public-side: upcoming + past listings with detail pages

### `projects` — branch projects
- `Project` (name, status, budget, description, started/ended, beneficiaries)
- Expense FK from `finances.Expense` for budget vs actual
- Image gallery via `Album`

### `reports` — document hub
- `Report` (title, type, year, file, description, uploaded_at, created_by)
- File upload validation: PDF/DOCX only, ≤10MB, virus-scan via clamav if available
- Public-facing read access; officer-side upload/manage

### `communications` — outreach
- `Message` model: subject, body, sender (User), audience filter spec, sent_at, status
- `Notification` model: per-user, read/unread, links to source object
- Email backend: SMTP via env (skymesh mail server initially; swap to Mailgun/SendGrid later if volume warrants)
- In-system inbox in member portal
- Targeting: by role, by school, by sub-county, by membership status, by event RSVP list

### `audits` — change tracking
- `django-auditlog` registered against: `User` (role changes), `Member`, `FinancialContribution`, `Expense`, `BankAccount`, `Report`
- Read-only viewer in officer console, scoped to admin and executive_secretary

### `welfare` — member welfare claims **(added per client confirmation)**
- `WelfareClaim` model: claimant (Member FK), category (bereavement, illness, accident, retirement gift, other), amount_requested, description, supporting_docs (file uploads), status (submitted/under_review/approved/rejected/paid), submitted_at, reviewed_by, reviewed_at, reviewer_notes
- Member side: submit claim with supporting documents (max 3 files, PDF/JPG/PNG, ≤5MB each), view own claim status
- Officer side: review queue, status transitions, link approved claim to an `Expense` for finance reconciliation
- Visible roles: `executive_secretary`, `chairperson`, `treasurer`, and a new `welfare_officer` role flag
- Audit log: every status transition logged with who/when/why

### `discipline` — disciplinary records **(added per client confirmation)**
This is the **most security-sensitive module** in the system. Treated like medical records architecturally.
- `DisciplinaryCase` model: subject (Member FK), case_number (auto-generated, unsequential to prevent enumeration), category, summary, status (opened/under_investigation/hearing_scheduled/resolved/appealed/closed), opened_at, opened_by, closed_at, outcome
- `DisciplinaryEvent` model: case FK, event_type, notes, occurred_at, recorded_by, attachments
- **Strict access tier:** only `chairperson`, `executive_secretary`, and an explicit `discipline_committee_member` flag. Treasurer and other officers do **not** see this module at all (no menu item, no URL discovery).
- Audit log retention: **permanent**, never purged
- Field-level encryption (Postgres `pgcrypto` or Django `django-cryptography`) for the `notes` and `summary` text
- All views require recent re-authentication (last login within 15 min) for the discipline section
- Subject (the member) has a view-only "my disciplinary history" page in their portal — they can see cases against them, but not internal committee notes
- Audit-log viewer for discipline is scoped to chairperson + executive_secretary only

### `core` — shared utilities
- `constants.py`: ROLES, ROLE_GROUPS (e.g. `LEADERSHIP_ROLES`, `FINANCE_ROLES`, `DISCIPLINE_ROLES`, `WELFARE_ROLES`)
- `mixins.py`: `RoleRequiredMixin`, `role_required` decorator, `RecentLoginRequiredMixin` (for discipline views)
- `models.py`: `TimeStampedModel` abstract base
- `utils.py`: PDF receipt generation, CSV import helpers, onboarding-tour state tracking

## 5. Non-functional requirements

**Security**
- HTTPS-only; HSTS preload-eligible after launch stability
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS` set in prod
- `SECRET_KEY`, JWT signing key, DB creds, Mpesa keys, SMTP creds all from env via `python-decouple`
- CSRF on every form; rate limiting on login, password reset, contact form via `django-ratelimit`
- File upload validation: extension whitelist, magic-byte sniffing, size cap, `DATA_UPLOAD_MAX_MEMORY_SIZE` set conservatively
- 2FA mandatory for finance and discipline roles
- **JWT access tokens ≤ 15 min; refresh tokens blacklisted on logout via Redis**
- **API throttling per scope (anon, user, login, discipline)**
- **Swagger/Redoc/schema endpoints gated to officers — never publicly enumerable**
- **Discipline endpoints conditionally stripped from OpenAPI schema based on caller role**
- **Field-level encryption** (`django-cryptography` over pgcrypto) on disciplinary case notes/summaries
- **Recent-authentication gate** (JWT issued within last 15 min, or re-entered password) for the discipline and finance-write endpoints
- Audit log retention ≥ 2 years general; **permanent** for discipline records

**Performance**
- Pagination on every list view (default 25)
- `select_related` / `prefetch_related` on every queryset that touches a FK
- Redis cache for public homepage aggregates (5 min TTL) and the transparency page (15 min TTL)
- Image processing: auto-resize on upload to ≤ 1600px wide, generate thumbnails

**Reliability**
- Daily `pg_dump` to off-VPS storage (rclone to a separate skymesh bucket or external S3)
- Weekly restore-test (automated, against a scratch DB)
- Documented disaster-recovery runbook

**Observability**
- Sentry free tier for errors
- Gunicorn access logs to file with logrotate
- Postgres slow-query log enabled

**Privacy & compliance**
- Align with **Kenya Data Protection Act 2019**: lawful basis for processing, consent on signup, right to access/correct/delete, breach-notification procedure
- PII minimization: don't store what we don't need; mask sensitive fields in logs
- A `PRIVACY.md` policy page linked from the public footer

## 6. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Django 5.2 LTS | v1 already uses it; mature; you know it |
| DB | Postgres 16 | Real DB; v1 already uses psycopg2 |
| Cache / queue | Redis 7 | Used for cache, JWT blacklist lookups, optional Celery later |
| Web server | gunicorn + nginx | Standard, well-documented on Ubuntu VPS |
| Static | whitenoise | Already in v1 stack; no nginx static config needed |
| Media | filesystem → S3-compatible later | Keep simple at launch |
| Auth (web) | django-allauth | Saves a week of building signup/verify/reset |
| **API framework** | **Django REST Framework** | Full REST across every module |
| **API auth** | **djangorestframework-simplejwt** | Short-lived access + refresh tokens, mobile-ready, blacklist on logout |
| **API docs** | **drf-spectacular** | OpenAPI 3 schema + Swagger UI + Redoc; better than drf-yasg, actively maintained |
| **API throttle** | **DRF built-in throttling** | Per-user and per-anon rate limits |
| Audit | django-auditlog | Battle-tested; minimal config |
| Forms | django-crispy-forms + bootstrap 5 | v1 already uses it |
| Filters | django-filter | v1 already uses it; also wires into DRF filtering |
| Frontend | Django templates + Bootstrap 5 + HTMX (selective) | No SPA, no build pipeline complexity |
| PDF | WeasyPrint (receipts) | Better than reportlab for HTML-to-PDF |
| Env config | python-decouple | Cleaner than dotenv-only |
| Tests | pytest-django + coverage + DRF test client | Already 313 lines in v1; expand |
| CI | GitHub Actions | Free for public repos |
| Error tracking | Sentry (free tier) | 5k events/month is enough |
| Uptime | UptimeRobot | Free tier sufficient |

**Deliberately NOT included for v2:**
- Celery — defer until there's a real async need (Mpesa callbacks are sync-able)
- Channels / WebSockets — nothing real-time required
- Docker — skymesh VPS deploy is simpler with venv + systemd; can dockerize later

## 7. Data model highlights

Key entities and their relationships (full ERD in `docs/erd.md`):

- `User` (1) — (0..1) `Member`: a member may or may not have a login account
- `Member` (1) — (*) `FinancialContribution`: member dues, donations, fees
- `Member` (1) — (*) `WelfareClaim`: claims raised by the member
- `Member` (1) — (*) `DisciplinaryCase` (as subject): cases against the member
- `WelfareClaim` (1) — (0..1) `Expense`: approved claims linked to disbursement
- `DisciplinaryCase` (1) — (*) `DisciplinaryEvent`: timeline of case activity
- `Project` (1) — (*) `Expense`: budget tracking
- `Event` (m) ↔ (m) `Member` through `EventAttendance`: RSVPs
- `Event` (1) — (0..1) `Album`: event photo gallery
- `Album` (1) — (*) `MediaItem`: photos/videos
- `Election` (1) — (*) `Candidate`: campaign info
- `Manifesto` (1) — (*) `ManifestoVersion`: historical campaign documents
- `User` (1) — (*) `Message` (as sender): outbound comms
- `User` (1) — (*) `Notification`: inbox
- `*` ← `AuditLogEntry`: tracks changes on registered models

## 8. M-Pesa integration plan

Daraja API integration ships **code-complete** but with stub credentials. **Decision locked: branch-owned Paybill.** When the chapter activates the merchant account, swap in:

```
MPESA_CONSUMER_KEY=
MPESA_CONSUMER_SECRET=
MPESA_PAYBILL=
MPESA_PASSKEY=
MPESA_CALLBACK_URL=https://kuppetmombasa.co.ke/mpesa/callback/
MPESA_VALIDATION_URL=https://kuppetmombasa.co.ke/mpesa/validate/
MPESA_CONFIRMATION_URL=https://kuppetmombasa.co.ke/mpesa/confirm/
MPESA_ENV=sandbox  # or 'production'
```

Three flows:

1. **C2B (Paybill — primary):** members pay directly to the branch Paybill using their **membership ID as the account reference**. The confirmation webhook creates a `FinancialContribution`, auto-reconciles by membership ID, and credits the right member. Unmatched references (wrong account ref, unknown member) land in a treasurer review queue.
2. **STK Push (secondary):** member logs into the portal, enters amount + contribution type, system pushes STK prompt to their phone. Same backing Paybill; just a smoother UX for members already in the app.
3. **Manual override:** treasurer can record an off-system payment (cash, bank transfer) and reconcile it against an unmatched Mpesa ref if needed.

Before activation, a stub adapter logs intended actions to the audit log — useful for testing the rest of the system without live credentials. The Paybill number and member-ID convention should be communicated to members via the public site footer and in welcome emails.

## 9. REST API & documentation

Every module exposes a REST API. The web UI consumes the same backend as any future mobile/external client — no parallel codepaths.

**Authentication: JWT (`djangorestframework-simplejwt`)**

- `/api/auth/token/` — obtain access + refresh tokens (login)
- `/api/auth/token/refresh/` — rotate access token
- `/api/auth/token/blacklist/` — logout (invalidates refresh)
- Access token TTL: **15 minutes**
- Refresh token TTL: **7 days** (sliding; rotates on use)
- Blacklist stored in Redis for fast revocation checks
- For sensitive endpoints (discipline, finance writes, role changes): **recent-auth claim** required — JWT must have been issued within the last 15 minutes. Stale JWTs prompt a re-login at the API layer.

**Authorization**

- DRF permission classes built from `core.constants.ROLES` and `ROLE_GROUPS` — same source of truth as the web views
- Object-level permissions where needed (e.g. a member can read their own contributions but not others')
- Discipline endpoints behind a custom `IsDisciplineCommittee` permission that checks role + recent-auth + 2FA status

**API surface (versioned under `/api/v1/`)**

| Module | Resources exposed | Notes |
|---|---|---|
| `accounts` | `me`, password change, 2FA enrollment | Member self-service |
| `members` | `members` (CRUD, filtered by role), `members/me` | Officers can list; members get only their own record |
| `finances` | `contributions`, `expenses`, `bank-accounts`, `transparency` (read-only aggregates) | Transparency endpoint is public (no auth) |
| `events` | `events`, `events/{id}/rsvp`, `events/{id}/attendance` | Public can read events; members RSVP; officers mark attendance |
| `projects` | `projects` | Public read, officer write |
| `reports` | `reports` | Public read on published; officer manages |
| `welfare` | `claims`, `claims/{id}/transitions` | Members submit; officers review |
| `discipline` | `cases`, `cases/{id}/events`, `cases/{id}/my-view` | Strict gating; encrypted payloads; permanent audit |
| `communications` | `messages`, `notifications`, `notifications/{id}/read` | Officers broadcast; members receive |
| `public_site` | `leaders`, `manifesto`, `transparency`, `gallery`, `contact` | All read-only, public |
| `mpesa` | `callback`, `validate`, `confirm`, `stk-push` | Webhook endpoints (Safaricom IP-whitelisted) + member-initiated STK |

**Throttling (DRF built-in)**

| Scope | Limit | Why |
|---|---|---|
| Anon | 60/hour | Public browsing tolerable, abuse expensive |
| Authenticated user | 1000/hour | Generous for normal use |
| Login attempts | 10/hour per IP | Brute-force protection |
| Mpesa webhook | unthrottled (IP-whitelisted to Safaricom) | Safaricom retries on 429 |
| Discipline endpoints | 30/hour per user | Discourages enumeration |

**Documentation: drf-spectacular**

- OpenAPI 3 schema auto-generated from serializers + viewsets
- Swagger UI at `/api/docs/` — **gated to officers only** (login + role check, not just authenticated)
- Redoc at `/api/redoc/` — same gate
- Schema endpoint at `/api/schema/` — same gate (so the spec itself isn't leaked)
- Members and the public **do not see the API exists** — no link from the public site, no link from the member portal
- Discipline endpoints appear in the schema only to users with `discipline_committee_member` flag; for everyone else they're stripped from the spec

**What the API does *not* expose**

- Discipline case **notes/summaries** are returned encrypted-at-rest and decrypted server-side; the API never returns the raw `pgcrypto` ciphertext
- Audit log mutation endpoints — audit log is **read-only** even via API; only signals/auditlog writes
- Admin operations (creating superusers, etc.) — admin-only via Django admin, not the API

**Testing**

- DRF `APIClient` test class per module
- Coverage target: 80% on viewsets, 90% on permission classes (the highest-risk code)
- Contract tests: schema diffs detected in CI; breaking changes require version bump



## 10. Deployment plan (skymesh.co.ke → kuppetmombasa.co.ke)

Assuming skymesh provides an Ubuntu LTS VPS with root SSH:

1. Provision: Ubuntu 24.04, 2 vCPU / 4GB RAM minimum, 40GB SSD
2. System packages: nginx, postgresql-16, python3.12, redis-server (optional), certbot, ufw, fail2ban
3. App user: non-root `kuppet` user, app at `/var/www/kuppetmsa/`
4. Python: venv per release, `pip install -r requirements.txt`
5. Postgres: dedicated DB and role, password from env
6. Gunicorn: systemd service, 3 workers, unix socket
7. nginx: reverse proxy, static via whitenoise (or nginx-served from `STATIC_ROOT`)
8. SSL: certbot for `kuppetmombasa.co.ke` and `www.kuppetmombasa.co.ke`, auto-renew
9. Firewall: ufw allow 22, 80, 443 only
10. Backups: nightly cron → `pg_dump | gzip | rclone copy` to off-VPS bucket
11. Monitoring: Sentry DSN in env, UptimeRobot ping every 5 min
12. Deployment: GitHub Actions runs tests, builds, then SSHes to VPS, pulls, migrates, collects static, restarts gunicorn

Full runbook in `docs/DEPLOYMENT.md`.

## 11. Sprint plan

Conservative estimate at part-time pace (evenings + weekends) — compress proportionally if full-time. DRF is *not* a separate phase — it's woven into every module phase, because building a serializer/viewset alongside the server-rendered view is cheaper than retrofitting later. There's a dedicated API hardening phase before launch to cover schema review, throttle tuning, and Swagger gating.

| Phase | Days | Deliverable |
|---|---|---|
| **0. Foundation** | 4 | Fresh project, settings split, env config, base templates, auth flows working end-to-end, DRF + simplejwt + drf-spectacular installed, `/api/v1/` router, `/api/auth/token/` working, Swagger UI rendering (gated to officers) |
| **1. Members + officers** | 6 | Member model + admin + import, officer console skeleton, RBAC enforcement from `core.constants`, **`members` viewset + `me` endpoint + permission classes** |
| **2. Finances core** | 7 | Contributions, expenses, audit log wired, officer recording UI, basic public transparency page, **`finances` viewsets, public `transparency` endpoint, recent-auth gate for writes** |
| **3. M-Pesa scaffolding** | 4 | C2B Paybill webhook + STK Push code, reconciliation by membership ID, stub adapter — these are already API endpoints |
| **4. Events + projects + reports** | 7 | Three modules CRUD on web + API, RSVP endpoint, file upload validation on report API |
| **5. Member portal** | 5 | Self-service dashboard, profile edit, contribution history, RSVPs, inbox — **all consuming the v1 API** so we dogfood it early |
| **6. Welfare** | 4 | Claim submission, review queue, status workflow, link-to-expense, **`welfare` API with state-transition endpoints** |
| **7. Discipline** | 5 | Restricted module, field-level encryption, recent-auth gate, member-side read-only view, **`discipline` API with conditional schema exposure** |
| **8. Communications** | 5 | Broadcast email, in-system inbox, notification model, targeting filters, **notification API for future mobile push** |
| **9. Public site polish** | 4 | Transparency dashboard with charts, gallery, leaders, manifesto viewer/versioning, contacts |
| **10. Onboarding & training** | 3 | In-app tour (driver.js), public "how to use" page, officer-guide.md with screenshots, **API reference handout for any future developer** |
| **11. API hardening** | 4 | Schema review, throttle tuning, Swagger gating verified, contract tests in CI, JWT blacklist on logout verified, recent-auth claim enforced on sensitive endpoints |
| **12. Security hardening** | 3 | Pen-test pass (CSRF, XSS, IDOR, auth bypass, JWT replay, schema enumeration), perf tuning, a11y check, docs |
| **13. Launch** | 2 | Deploy to kuppetmombasa.co.ke, smoke test, training sessions with officers |

**Total: ~63 working days** (≈ 9–10 weeks full-time, ≈ 16–18 weeks part-time).

Each phase ends with: tests passing (both server-rendered views *and* API endpoints), demo to client, sign-off before moving on. No big-bang launches.

## 12. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Sole maintainer (bus factor = 1) | High | High | Thorough README, inline comments, DEPLOYMENT.md, runbook; consider pairing a junior dev for handover |
| Client cash flow uncertainty | Medium | Medium | Self-fund through phase 5, lock in client commitment before phase 6 |
| Mpesa credentials delayed | High | Low | Stub adapter means launch isn't blocked |
| KUPPET role taxonomy changes | Medium | Low | Single constants module; one-PR fix |
| Scope creep from officers | High | Medium | Maintain a v1.1 backlog; nothing new mid-sprint |
| skymesh VPS limitations | Unknown | Medium | Confirm VPS specs and Postgres support **before phase 10** |
| Data protection compliance | Medium | High | PRIVACY.md, consent on signup, breach plan in runbook |
| **JWT signing key leak** | Low | Critical | Key from env, rotated on suspicion; all refresh tokens invalidated via blacklist |
| **Swagger schema leaks sensitive endpoints** | Medium | High | Gate at view level + conditional schema generation per caller role; verify in phase 11 |
| **API throttling too loose (DoS)** | Medium | Medium | Per-scope throttles set conservatively; tune in phase 11 with realistic load test |
| **Full DRF doubles maintenance surface** | High | Medium | Strict serializer/permission patterns; shared base classes; 80%+ test coverage on viewsets |

## 13. Client decisions (confirmed)

Answers locked in with the client. These shape the build:

1. **Membership size** — scope assumes "every TSC-employed post-primary teacher in Mombasa County" as the addressable population. Realistically that's in the **low thousands** (~3,000–5,000 working figure; refine when the branch shares their registry). System sized for **10,000 members and 200 concurrent users** to give headroom.
2. **M-Pesa** — branch-owned **Paybill**. Members pay to a single shortcode using their **membership ID as the account reference**. C2B confirmation webhook is the primary integration; STK Push is the secondary convenience flow from the member portal.
3. **Email sender** — `noreply@kuppetmombasa.co.ke` for v2. Sender domain configurable via env (`DEFAULT_FROM_EMAIL`) so it can change without a code release.
4. **Welfare module** — **in scope for v2**. See §4 addendum below.
5. **Manifestos** — admins and designated staff (officers with a new `manifesto_editor` role flag, separate from constitutional roles) can edit; public reads only. Elections occur infrequently (typically every 5 years per KUPPET constitution), so we don't optimize for live election operations — but we do version manifestos so historical campaigns remain visible.
6. **Disciplinary records** — **in scope for v2**. See §4 addendum below. This is the most security-sensitive module in the system and gets its own access tier.
7. **Training** — two-track:
   - **Officer training:** 1-on-1 walkthrough session per officer role, ~30–45 min each. Backed by an `docs/officer-guide.md` with screenshots.
   - **Member onboarding:** in-app guided tour on first login (using a lightweight library like `driver.js`), plus a public "How to use this site" page with short video clips.
8. **Handover plan** — **no formal handover yet.** This is a known risk (bus factor = 1). Mitigations in §11 still apply: thorough README, runbook, inline comments, plus a tagged v2.0 release with frozen dependencies so anyone picking it up later has a clean reference point. Revisit when/if the client engages a second developer.

## 14. v2.1 backlog (out of scope, but tracked)

Stuff that will come up — capture now, build later:

- SMS broadcasts via Africa's Talking
- Mobile app (React Native or PWA install)
- Public REST API for partner organizations
- Online voting (separate security review needed)
- Multi-branch (i.e. county) instances
- Document signing / e-signatures on resolutions
- Member-to-member messaging (currently officers → members only)
- Advanced finance reporting / exports for auditors
- Calendar feed (iCal) for events
- Formal handover artifacts (when client engages a second developer)

---

**Next step:** review this with the client, get answers to §12, then we cut a clean repo and start Phase 0.
