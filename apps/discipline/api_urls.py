"""API routes for the discipline app.

The committee router lives under /cases/; the subject's redacted view is
a separate, deliberately minimal path.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.discipline.views import (
    DisciplinaryCaseViewSet,
    MyDisciplinaryCasesView,
)

app_name = "discipline"

router = DefaultRouter()
router.register("cases", DisciplinaryCaseViewSet, basename="case")

urlpatterns = [
    path(
        "my-cases/",
        MyDisciplinaryCasesView.as_view(),
        name="my-cases",
    ),
    *router.urls,
]
