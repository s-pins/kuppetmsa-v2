# KUPPET MSA — Permissions matrix

**Status:** v0.1 — for chairperson sign-off before code begins
**Source of truth:** this document drives `core/constants.py`. If the matrix and the code drift, the matrix wins and the code gets fixed.

---

## 1. Reading this document

Three things define what a user can do:

1. **Role** — their constitutional position (chairperson, treasurer, etc.). One person, one primary role.
2. **Flags** — optional extra capabilities layered on top of role (e.g. `discipline_committee_member`, `welfare_officer`, `manifesto_editor`). One person can have multiple flags.
3. **Subject relationship** — whether they own the data (e.g. "my own contributions" vs "any contribution").

A permission check answers: *can this user perform this action on this object?*

## 2. Roles (constitutional positions)

These mirror the KUPPET branch constitution. One per user. Stored as `User.role`.

| Code | Display | Notes |
|---|---|---|
| `admin` | System administrator | Technical superuser; not a constitutional role |
| `chairperson` | Chairperson | Branch head |
| `vice_chairperson` | Vice chairperson | |
| `executive_secretary` | Executive secretary | Day-to-day branch operations |
| `assistant_executive_secretary` | Assistant executive secretary | |
| `treasurer` | Treasurer | Holds the keys to the money |
| `assistant_treasurer` | Assistant treasurer | |
| `organizing_secretary` | Organizing secretary | Events, mobilization |
| `secretary_secondary` | Secretary, secondary sector | (note: v1 had typo `secretay_secondary`) |
| `secretary_tertiary` | Secretary, tertiary sector | |
| `secretary_junior_school` | Secretary, junior school sector | |
| `secretary_gender` | Secretary, gender affairs | |
| `gender_assistant_1st` | 1st gender assistant | |
| `gender_plwds_2nd` | 2nd gender assistant (PLWDs) | |
| `gender_youth_3rd` | 3rd gender assistant (Youth) | |
| `member` | Ordinary member | Default for any non-officer with a login |
| `public` | (anonymous) | Not a stored role — used in matrix only |

## 3. Flags (additive capabilities)

Stored as boolean fields on `User`. Independent of role.

| Flag | Purpose | Typically granted to |
|---|---|---|
| `discipline_committee_member` | Access to discipline module | Chairperson + 2–3 appointed officers |
| `welfare_officer` | Welfare review queue (in addition to default welfare reviewers) | Appointed welfare committee |
| `manifesto_editor` | Edit candidate manifestos during election cycles | Admin + designated campaign staff |
| `finance_2fa_enrolled` | Computed: 2FA is active | Required for finance & discipline access |

**Rule:** if a check requires both role *and* flag (e.g. discipline access), missing either denies the action. No "soft" overrides.

## 4. Role groups (defined in `core/constants.py`)

Reusable sets to keep permission code DRY. **These are the only groupings code should reference.** Never check role membership inline.

```python
LEADERSHIP_ROLES = {
    'admin', 'chairperson', 'vice_chairperson',
    'executive_secretary', 'assistant_executive_secretary',
}

FINANCE_ROLES = {
    'admin', 'treasurer', 'assistant_treasurer',
}

FINANCE_VIEW_ROLES = FINANCE_ROLES | {
    'chairperson', 'executive_secretary',
}  # can view but not write

OFFICER_ROLES = {
    'admin', 'chairperson', 'vice_chairperson',
    'executive_secretary', 'assistant_executive_secretary',
    'treasurer', 'assistant_treasurer',
    'organizing_secretary',
    'secretary_secondary', 'secretary_tertiary',
    'secretary_junior_school', 'secretary_gender',
    'gender_assistant_1st', 'gender_plwds_2nd', 'gender_youth_3rd',
}

EVENT_ORGANIZER_ROLES = {
    'admin', 'organizing_secretary',
    'chairperson', 'executive_secretary',
}

COMMUNICATIONS_ROLES = {
    'admin', 'chairperson', 'executive_secretary',
    'organizing_secretary',
}

# Discipline is intentionally NOT a role group — it's role + flag.
# Treated separately in code to enforce the layered check.
```

## 5. Permissions matrix

**Legend:**
- ✅ = allowed
- ❌ = denied (no access, hidden from UI, stripped from API schema)
- 👁 = read-only
- 🔒 = allowed but requires recent re-authentication (≤15 min)
- 🔑 = allowed but requires 2FA enrollment
- *self* = only on records owned by the user

Each row is one action. **If an action isn't listed, it's denied by default.** Open the door explicitly or it stays shut.

### 5.1 Accounts & profiles

| Action | Public | Member | Officer (generic) | Leadership | Admin |
|---|---|---|---|---|---|
| Sign up (self-registration) | ✅ | — | — | — | — |
| Verify email | ✅ | — | — | — | — |
| Reset own password | ❌ | ✅ | ✅ | ✅ | ✅ |
| Enroll 2FA | ❌ | ✅ | ✅ | ✅ | ✅ |
| View own profile | ❌ | ✅ | ✅ | ✅ | ✅ |
| Edit own profile (safe fields) | ❌ | ✅ | ✅ | ✅ | ✅ |
| View any user's profile | ❌ | ❌ | 👁 | ✅ | ✅ |
| Change another user's role | ❌ | ❌ | ❌ | ❌ | 🔒 ✅ |
| Deactivate user account | ❌ | ❌ | ❌ | ✅ | ✅ |
| Grant/revoke flags | ❌ | ❌ | ❌ | 🔒 ✅ | 🔒 ✅ |
| Force-reset another's password | ❌ | ❌ | ❌ | ❌ | 🔒 ✅ |

### 5.2 Members module

| Action | Public | Member | Officer | Leadership | Admin |
|---|---|---|---|---|---|
| View public member directory (name, school, role only) | ✅ | ✅ | ✅ | ✅ | ✅ |
| View full member record (TSC, ID, phone) | ❌ | self | ✅ | ✅ | ✅ |
| Create member | ❌ | ❌ | ❌ | ✅ | ✅ |
| Edit member (admin fields: TSC, status) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Edit member (safe fields: contact, photo, bio) | ❌ | self | self | ✅ | ✅ |
| Bulk import (CSV) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Export member list | ❌ | ❌ | ❌ | ✅ | ✅ |
| Deactivate member | ❌ | ❌ | ❌ | ✅ | ✅ |

### 5.3 Finances module

`FINANCE_ROLES` = treasurer + assistant_treasurer + admin. `FINANCE_VIEW_ROLES` adds chairperson + executive_secretary as read-only.

| Action | Public | Member | Officer | Finance view | Finance write | Admin |
|---|---|---|---|---|---|---|
| View public transparency aggregates | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View own contributions | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View any member's contributions | ❌ | ❌ | ❌ | 👁 | ✅ | ✅ |
| Record contribution (manual entry) | ❌ | ❌ | ❌ | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Edit contribution (within 24h, audit-logged) | ❌ | ❌ | ❌ | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Reverse contribution (after 24h) | ❌ | ❌ | ❌ | ❌ | ❌ | 🔒🔑 ✅ |
| View all expenses | ❌ | ❌ | ❌ | 👁 | ✅ | ✅ |
| Create expense | ❌ | ❌ | ❌ | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Approve expense > KES 50,000 | ❌ | ❌ | ❌ | ❌ | ❌ | needs chairperson co-sign (see §6) |
| View bank accounts | ❌ | ❌ | ❌ | 👁 | ✅ | ✅ |
| Edit bank account details | ❌ | ❌ | ❌ | ❌ | ❌ | 🔒🔑 ✅ |
| Trigger Mpesa STK Push from portal | ❌ | self | self | self | self | self |
| Receive Mpesa C2B webhook | webhook is unauthenticated but IP-whitelisted to Safaricom + signature-validated |
| Manually reconcile unmatched Mpesa ref | ❌ | ❌ | ❌ | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Download contribution receipt (PDF) | ❌ | self | self | ✅ | ✅ | ✅ |

### 5.4 Events module

| Action | Public | Member | Officer (any) | Event organizer | Admin |
|---|---|---|---|---|---|
| View upcoming events | ✅ | ✅ | ✅ | ✅ | ✅ |
| View past events with photos | ✅ | ✅ | ✅ | ✅ | ✅ |
| RSVP to event | ❌ | ✅ | ✅ | ✅ | ✅ |
| Cancel own RSVP | ❌ | ✅ | ✅ | ✅ | ✅ |
| View attendee list | ❌ | ❌ | ❌ | ✅ | ✅ |
| Create event | ❌ | ❌ | ❌ | ✅ | ✅ |
| Edit event | ❌ | ❌ | ❌ | ✅ | ✅ |
| Mark attendance | ❌ | ❌ | ❌ | ✅ | ✅ |
| Delete event | ❌ | ❌ | ❌ | ❌ | ✅ |
| Attach photo album | ❌ | ❌ | ❌ | ✅ | ✅ |

`EVENT_ORGANIZER_ROLES` = organizing_secretary + chairperson + executive_secretary + admin.

### 5.5 Projects module

| Action | Public | Member | Officer | Leadership | Admin |
|---|---|---|---|---|---|
| View project list (public projects) | ✅ | ✅ | ✅ | ✅ | ✅ |
| View project budget vs actual | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create project | ❌ | ❌ | ❌ | ✅ | ✅ |
| Edit project | ❌ | ❌ | ❌ | ✅ | ✅ |
| Update project status | ❌ | ❌ | ❌ | ✅ | ✅ |
| Tag expense to project | ❌ | ❌ | ❌ | finance_write only | ✅ |
| Delete project | ❌ | ❌ | ❌ | ❌ | ✅ |

### 5.6 Reports module

| Action | Public | Member | Officer | Leadership | Admin |
|---|---|---|---|---|---|
| View published reports | ✅ | ✅ | ✅ | ✅ | ✅ |
| View draft/unpublished reports | ❌ | ❌ | uploader only | ✅ | ✅ |
| Upload report | ❌ | ❌ | ✅ | ✅ | ✅ |
| Publish report (make public) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Edit own uploaded report | ❌ | ❌ | uploader only | ✅ | ✅ |
| Delete report | ❌ | ❌ | ❌ | ❌ | ✅ |

### 5.7 Welfare module

| Action | Public | Member | Officer | Welfare reviewer | Leadership | Admin |
|---|---|---|---|---|---|---|
| Submit welfare claim | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View own claims | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View all open claims | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Move claim to under_review | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Approve claim ≤ KES 20,000 | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Approve claim > KES 20,000 | ❌ | ❌ | ❌ | ❌ | 🔒 ✅ | 🔒 ✅ |
| Reject claim with reason | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Mark claim as paid (links to Expense) | ❌ | ❌ | ❌ | ❌ | finance_write only | 🔒 ✅ |
| Withdraw own claim | ❌ | ✅ (own, while submitted only) | self | self | ✅ | ✅ |
| Edit reviewer notes | ❌ | ❌ | ❌ | own notes only | ✅ | ✅ |

"Welfare reviewer" = user with `welfare_officer` flag OR role in `LEADERSHIP_ROLES`.

### 5.8 Discipline module — restricted

**Every action in this section requires:**
1. Role in `{chairperson, executive_secretary, admin}` OR `discipline_committee_member = True`
2. 2FA enrolled and active
3. Recent authentication (≤15 min)

If any of those three are missing, the module **does not appear in the UI** and **API endpoints return 404 (not 403 — we don't confirm existence)**.

| Action | Member (subject) | Discipline committee | Chairperson | Admin |
|---|---|---|---|---|
| Open a case | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| View case list | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| View case detail (encrypted notes) | own cases, summary only | 🔒🔑 ✅ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Add case event/timeline entry | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Edit case event (within 1 hour, audited) | ❌ | 🔒🔑 own entries | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Change case status | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Close case | ❌ | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Reopen closed case | ❌ | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| View case audit log | ❌ | 🔒🔑 ✅ | 🔒🔑 ✅ | 🔒🔑 ✅ |
| Delete case | ❌ | ❌ | ❌ | ❌ (never — only close) |
| View "my disciplinary history" (subject view) | 🔒 ✅ summary only | n/a | n/a | n/a |

**Notes on the subject view:**
- A member subject to a case sees: case number, category, status, opened date, closed date, outcome (if resolved).
- They do **not** see: internal committee notes, individual event details, who recorded what, attached evidence.
- Subject view requires recent auth too — protects against shoulder-surfing.

### 5.9 Communications module

| Action | Public | Member | Officer | Comms role | Admin |
|---|---|---|---|---|---|
| View public announcements (homepage) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Receive broadcast email | ❌ | ✅ | ✅ | ✅ | ✅ |
| View own inbox | ❌ | ✅ | ✅ | ✅ | ✅ |
| Mark notification as read | ❌ | self | self | self | self |
| Update notification preferences | ❌ | ✅ | ✅ | ✅ | ✅ |
| Compose broadcast (email + inbox) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Target broadcast by role/school/sub-county | ❌ | ❌ | ❌ | ✅ | ✅ |
| View sent-message log | ❌ | ❌ | ❌ | own only | ✅ |
| Re-send failed broadcast | ❌ | ❌ | ❌ | own only | ✅ |

`COMMUNICATIONS_ROLES` = chairperson + executive_secretary + organizing_secretary + admin.

### 5.10 Public site & manifestos

| Action | Public | Member | Officer | Manifesto editor | Admin |
|---|---|---|---|---|---|
| View leaders page | ✅ | ✅ | ✅ | ✅ | ✅ |
| View transparency dashboard | ✅ | ✅ | ✅ | ✅ | ✅ |
| View current manifesto | ✅ | ✅ | ✅ | ✅ | ✅ |
| View historical manifestos (archive) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Submit contact form (rate-limited) | ✅ | ✅ | ✅ | ✅ | ✅ |
| View contact submissions | ❌ | ❌ | ❌ | ❌ | ✅ (admin + executive_secretary) |
| Create new manifesto version | ❌ | ❌ | ❌ | ✅ | ✅ |
| Publish manifesto version (becomes current) | ❌ | ❌ | ❌ | ❌ | 🔒 ✅ (admin + chairperson) |
| Edit candidate info during election | ❌ | ❌ | ❌ | ✅ | ✅ |
| Delete manifesto/candidate | ❌ | ❌ | ❌ | ❌ | ❌ (archive only, never delete) |

### 5.11 System administration

| Action | Anyone | Officer | Leadership | Admin |
|---|---|---|---|---|
| Access Django admin (`/admin/`) | ❌ | ❌ | ❌ | 🔒🔑 ✅ |
| Access Swagger UI (`/api/docs/`) | ❌ | ✅ | ✅ | ✅ |
| Access API schema (`/api/schema/`) | ❌ | ✅ | ✅ | ✅ |
| View audit log (general) | ❌ | ❌ | ✅ | ✅ |
| View audit log (discipline scope) | ❌ | discipline committee only | chairperson + executive_secretary | ✅ |
| Export audit log | ❌ | ❌ | ❌ | 🔒 ✅ |
| Trigger database backup | ❌ | ❌ | ❌ | 🔒 ✅ |
| View Sentry errors | ❌ | ❌ | ❌ | ✅ |

## 6. Approval workflows (compound permissions)

Some actions require multiple parties to act. Recorded as state machines, not single permission checks.

### 6.1 Large expense approval
For any expense > **KES 50,000**:
1. Treasurer (finance_write) creates the expense in `proposed` state.
2. Chairperson reviews and either approves (→ `approved`) or rejects (→ `rejected`, with reason).
3. Only `approved` expenses appear in transparency aggregates.
4. Both actions are audit-logged with timestamps and rationale.

If the chairperson is also the treasurer (one person wearing two hats), the system **blocks the action**: a different leadership-role user must approve. Two-person rule.

### 6.2 Manifesto publication
1. Manifesto editor creates a new `ManifestoVersion` in `draft` state.
2. Chairperson reviews and publishes (→ sets `is_current = True`, demotes previous current to archive).
3. Previous versions remain readable forever.

### 6.3 User role assignment
1. Admin proposes a role change.
2. If the new role is in `FINANCE_ROLES` or grants `discipline_committee_member`, chairperson must co-confirm before it takes effect.
3. Until co-confirmed, the user has their previous permissions.

## 7. Implementation notes

- **Permission code lives in `core/permissions.py`** (DRF) and `core/mixins.py` (server-rendered views). Both import from `core/constants.py`. Same checks, two surfaces.
- **No string literals at call sites.** Never write `if user.role == 'chairperson'`. Always: `if user.role in LEADERSHIP_ROLES`.
- **Default-deny.** Every viewset starts with `permission_classes = [IsAuthenticated, ...]`. Public endpoints explicitly opt out via `[AllowAny]`.
- **Object-level checks** use DRF's `has_object_permission`. Never rely on filtering the queryset to enforce auth — always check the object too.
- **404 not 403** for the discipline module: leaking "this case exists, you just can't see it" is itself information disclosure.
- **Tests are mandatory** for every row in this matrix. `tests/test_permissions.py` will have one test per action per role. If we don't test it, it doesn't ship.

## 8. Sign-off

This matrix is binding. Changes to it after sign-off require:
1. Documented rationale.
2. Chairperson + executive_secretary email confirmation (audit trail).
3. Matrix updated, code updated, tests updated — same PR.

| Signatory | Role | Date | Signature |
|---|---|---|---|
| | Chairperson | | |
| | Executive secretary | | |
| | Treasurer | | |
| | Maintainer (developer) | | |

---

**Reviewer checklist before signing:**
- [ ] Every action your office performs in real life appears somewhere in this matrix
- [ ] The KES thresholds (50k expense, 20k welfare) match branch policy
- [ ] The "two-person rule" on chairperson-as-treasurer is acceptable
- [ ] The 15-minute recent-auth window is workable for finance staff
- [ ] You're comfortable that members see *summary only* of their own discipline cases
- [ ] The discipline committee composition is settled (which 2–3 people get the flag)
