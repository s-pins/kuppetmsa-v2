"""Server-rendered member views for the officer console.

Uses the Phase 0 RoleRequiredMixin so the same constants drive both the
API permissions and the rendered pages.
"""

from django.views.generic import ListView

from apps.core.constants import OFFICER_ROLES
from apps.core.mixins import RoleRequiredMixin
from apps.members.models import Member


class MemberListView(RoleRequiredMixin, ListView):
    """Officer-facing paginated member directory."""

    allowed_roles = OFFICER_ROLES
    model = Member
    template_name = "members/member_list.html"
    context_object_name = "members"
    paginate_by = 25

    def get_queryset(self):
        qs = Member.objects.all().select_related("user")
        q = self.request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q

            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(membership_id__icontains=q)
                | Q(school__icontains=q)
            )
        active = self.request.GET.get("active")
        if active == "1":
            qs = qs.filter(is_active=True)
        elif active == "0":
            qs = qs.filter(is_active=False)
        return qs
