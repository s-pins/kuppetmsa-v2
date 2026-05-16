"""
Single source of truth for roles, flags, and role groups.

Every permission check in this codebase — DRF permissions, view mixins,
template tags — imports from this module. Never write `if user.role == 'chairperson'`
at a call site; always reference a constant or group from here.

The permissions matrix at docs/permissions.md is the human-readable
counterpart to this file. When you change one, change the other in the
same commit.
"""

# ---------------------------------------------------------------------------
# Constitutional roles. One per user.
# ---------------------------------------------------------------------------

ROLE_ADMIN = 'admin'
ROLE_CHAIRPERSON = 'chairperson'
ROLE_VICE_CHAIRPERSON = 'vice_chairperson'
ROLE_EXECUTIVE_SECRETARY = 'executive_secretary'
ROLE_ASSISTANT_EXECUTIVE_SECRETARY = 'assistant_executive_secretary'
ROLE_TREASURER = 'treasurer'
ROLE_ASSISTANT_TREASURER = 'assistant_treasurer'
ROLE_ORGANIZING_SECRETARY = 'organizing_secretary'
ROLE_SECRETARY_SECONDARY = 'secretary_secondary'        # v1 had typo 'secretay_secondary'
ROLE_SECRETARY_TERTIARY = 'secretary_tertiary'
ROLE_SECRETARY_JUNIOR_SCHOOL = 'secretary_junior_school'
ROLE_SECRETARY_GENDER = 'secretary_gender'
ROLE_GENDER_ASSISTANT_1ST = 'gender_assistant_1st'
ROLE_GENDER_PLWDS_2ND = 'gender_plwds_2nd'
ROLE_GENDER_YOUTH_3RD = 'gender_youth_3rd'
ROLE_MEMBER = 'member'

ROLE_CHOICES = [
    (ROLE_ADMIN, 'System administrator'),
    (ROLE_CHAIRPERSON, 'Chairperson'),
    (ROLE_VICE_CHAIRPERSON, 'Vice chairperson'),
    (ROLE_EXECUTIVE_SECRETARY, 'Executive secretary'),
    (ROLE_ASSISTANT_EXECUTIVE_SECRETARY, 'Assistant executive secretary'),
    (ROLE_TREASURER, 'Treasurer'),
    (ROLE_ASSISTANT_TREASURER, 'Assistant treasurer'),
    (ROLE_ORGANIZING_SECRETARY, 'Organizing secretary'),
    (ROLE_SECRETARY_SECONDARY, 'Secretary, secondary sector'),
    (ROLE_SECRETARY_TERTIARY, 'Secretary, tertiary sector'),
    (ROLE_SECRETARY_JUNIOR_SCHOOL, 'Secretary, junior school sector'),
    (ROLE_SECRETARY_GENDER, 'Secretary, gender affairs'),
    (ROLE_GENDER_ASSISTANT_1ST, '1st gender assistant'),
    (ROLE_GENDER_PLWDS_2ND, '2nd gender assistant (PLWDs)'),
    (ROLE_GENDER_YOUTH_3RD, '3rd gender assistant (Youth)'),
    (ROLE_MEMBER, 'Ordinary member'),
]

# ---------------------------------------------------------------------------
# Role groups. Compose call sites against these, never against literals.
# ---------------------------------------------------------------------------

LEADERSHIP_ROLES = frozenset({
    ROLE_ADMIN,
    ROLE_CHAIRPERSON,
    ROLE_VICE_CHAIRPERSON,
    ROLE_EXECUTIVE_SECRETARY,
    ROLE_ASSISTANT_EXECUTIVE_SECRETARY,
})

FINANCE_WRITE_ROLES = frozenset({
    ROLE_ADMIN,
    ROLE_TREASURER,
    ROLE_ASSISTANT_TREASURER,
})

FINANCE_VIEW_ROLES = FINANCE_WRITE_ROLES | frozenset({
    ROLE_CHAIRPERSON,
    ROLE_EXECUTIVE_SECRETARY,
})

OFFICER_ROLES = frozenset({
    ROLE_ADMIN,
    ROLE_CHAIRPERSON,
    ROLE_VICE_CHAIRPERSON,
    ROLE_EXECUTIVE_SECRETARY,
    ROLE_ASSISTANT_EXECUTIVE_SECRETARY,
    ROLE_TREASURER,
    ROLE_ASSISTANT_TREASURER,
    ROLE_ORGANIZING_SECRETARY,
    ROLE_SECRETARY_SECONDARY,
    ROLE_SECRETARY_TERTIARY,
    ROLE_SECRETARY_JUNIOR_SCHOOL,
    ROLE_SECRETARY_GENDER,
    ROLE_GENDER_ASSISTANT_1ST,
    ROLE_GENDER_PLWDS_2ND,
    ROLE_GENDER_YOUTH_3RD,
})

EVENT_ORGANIZER_ROLES = frozenset({
    ROLE_ADMIN,
    ROLE_ORGANIZING_SECRETARY,
    ROLE_CHAIRPERSON,
    ROLE_EXECUTIVE_SECRETARY,
})

COMMUNICATIONS_ROLES = frozenset({
    ROLE_ADMIN,
    ROLE_CHAIRPERSON,
    ROLE_EXECUTIVE_SECRETARY,
    ROLE_ORGANIZING_SECRETARY,
})

# Discipline access is role + flag, intentionally NOT a simple role group.
# Use the discipline_committee_member flag check in code.
DISCIPLINE_BASE_ROLES = frozenset({
    ROLE_ADMIN,
    ROLE_CHAIRPERSON,
    ROLE_EXECUTIVE_SECRETARY,
})

# ---------------------------------------------------------------------------
# Additive capability flags. Stored as booleans on the User model.
# ---------------------------------------------------------------------------

FLAG_DISCIPLINE_COMMITTEE = 'discipline_committee_member'
FLAG_WELFARE_OFFICER = 'welfare_officer'
FLAG_MANIFESTO_EDITOR = 'manifesto_editor'

# ---------------------------------------------------------------------------
# Security thresholds.
# Change these here, not at call sites.
# ---------------------------------------------------------------------------

# Window during which the user is considered "recently authenticated".
# Beyond this, sensitive operations re-prompt for password (web) or
# require a fresh JWT (API).
RECENT_AUTH_WINDOW_SECONDS = 15 * 60  # 15 minutes

# Expense ceiling above which chairperson must co-approve.
# Verify this against the branch financial regulations before launch.
LARGE_EXPENSE_THRESHOLD_KES = 50_000

# Welfare claim ceiling for auto-approval by welfare reviewer.
# Above this, leadership must approve.
WELFARE_AUTO_APPROVE_THRESHOLD_KES = 20_000

# JWT lifetimes — kept here so simplejwt config and tests reference one place.
JWT_ACCESS_LIFETIME_MINUTES = 15
JWT_REFRESH_LIFETIME_DAYS = 7
