"""Audit-log registration for discipline.

Critical: we track WHO did WHAT and the status/outcome transitions, but
we exclude the encrypted content fields (summary, notes) from the audit
diff. The whole point of field encryption is that the plaintext never
sits at rest anywhere — and an auditlog diff is "anywhere". The audit
trail records that a case advanced / an action was added and by whom;
the sensitive text stays only in the encrypted column.
"""

from auditlog.registry import auditlog

from apps.discipline.models import DisciplinaryAction, DisciplinaryCase

auditlog.register(
    DisciplinaryCase,
    exclude_fields=["summary", "created_at", "updated_at"],
)
auditlog.register(
    DisciplinaryAction,
    exclude_fields=["notes", "created_at", "updated_at"],
)
