"""Discipline API — docs/permissions.md §5.8. Highest-sensitivity module.

Design rules enforced here:

  1. The committee viewset returns 404 (never 403) when the
     IsDisciplineCommittee check fails — an unauthorised caller must not
     be able to distinguish "exists but forbidden" from "does not
     exist". We override permission failure -> NotFound.

  2. The subject ("my cases") path is a SEPARATE view with its own
     permission. A member sees only their own cases through the redacted
     serializer. It never touches the committee viewset, so there is no
     code path by which a subject reaches summaries or notes.

  3. Phase 2/6 lesson applied proactively: a viewset-wide permission
     must not silently over-restrict a privileged action. Here every
     committee action legitimately requires the SAME gate
     (IsDisciplineCommittee), so a single get_permissions is correct —
     but it is a conscious decision, documented, not an oversight.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import decorators, generics, mixins, response, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.core.permissions import IsDisciplineCommittee
from apps.discipline.models import DisciplinaryCase
from apps.discipline.serializers import (
    DisciplinaryActionSerializer,
    DisciplinaryCaseCreateSerializer,
    DisciplinaryCaseSerializer,
    MyCaseSummarySerializer,
)
from apps.portal.permissions import IsMemberWithProfile


class _MaskDeniedAs404Mixin:
    """Convert any auth/permission denial on this view into 404.

    Defence against existence disclosure: the discipline module must be
    invisible to anyone without committee access. DRF's default would
    leak 401/403 (which themselves confirm "there is something here").
    """

    def handle_exception(self, exc):
        if isinstance(exc, (PermissionDenied, NotFound)):
            return super().handle_exception(NotFound())
        # Unauthenticated -> NotAuthenticated would surface a 401; mask
        # that too.
        from rest_framework.exceptions import NotAuthenticated

        if isinstance(exc, NotAuthenticated):
            return super().handle_exception(NotFound())
        return super().handle_exception(exc)


class DisciplinaryCaseViewSet(
    _MaskDeniedAs404Mixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Committee-only. Every action requires the full
    role+flag+2FA+recent-auth gate (IsDisciplineCommittee)."""

    queryset = DisciplinaryCase.objects.select_related("subject", "opened_by").prefetch_related(
        "actions"
    )
    filterset_fields = ["status", "category", "outcome"]

    def get_permissions(self):
        # Single gate for ALL actions is intentional here (see module
        # docstring point 3): viewing, creating, transitioning and
        # logging actions on a disciplinary case are all equally
        # sensitive. This is not the Phase 2/6 over-restriction trap —
        # there is no privileged sub-action that needs a *different*
        # (broader) policy.
        return [IsDisciplineCommittee()]

    def get_serializer_class(self):
        if self.action == "create":
            return DisciplinaryCaseCreateSerializer
        return DisciplinaryCaseSerializer

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)

    # ---- state-machine actions -----------------------------------------

    def _transition(self, request, fn):
        case = self.get_object()
        try:
            fn(case)
        except DjangoValidationError as exc:
            return response.Response(
                {"detail": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(DisciplinaryCaseSerializer(case).data)

    @decorators.action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        to_status = request.data.get("to_status")
        if not to_status:
            return response.Response(
                {"detail": "to_status is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._transition(request, lambda c: c.advance(to_status))

    @decorators.action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        outcome = request.data.get("outcome")
        if not outcome:
            return response.Response(
                {"detail": "outcome is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._transition(request, lambda c: c.decide(outcome))

    @decorators.action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._transition(request, lambda c: c.close())

    @decorators.action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        return self._transition(request, lambda c: c.reopen())

    @decorators.action(detail=True, methods=["post"], url_path="add-action")
    def add_action(self, request, pk=None):
        """Append an immutable timeline entry (note/evidence/etc.)."""
        case = self.get_object()
        ser = DisciplinaryActionSerializer(data={**request.data, "case": case.pk})
        ser.is_valid(raise_exception=True)
        ser.save(recorded_by=request.user, case=case)
        return response.Response(ser.data, status=status.HTTP_201_CREATED)


class MyDisciplinaryCasesView(_MaskDeniedAs404Mixin, generics.ListAPIView):
    """The subject's own redacted view.

    Separate view, separate (member) permission, redacted serializer.
    There is intentionally no detail/action route here — a subject can
    enumerate their own cases' status/outcome and nothing more.
    """

    serializer_class = MyCaseSummarySerializer
    permission_classes = [IsMemberWithProfile]

    def get_queryset(self):
        return DisciplinaryCase.objects.filter(subject=self.request.user.member_profile).order_by(
            "-opened_at"
        )
