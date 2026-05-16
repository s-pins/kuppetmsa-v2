"""API routes for the finances app."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.finances.views import (
    BankAccountViewSet,
    ContributionViewSet,
    ExpenseViewSet,
    TransparencyView,
)

app_name = "finances"

router = DefaultRouter()
router.register("bank-accounts", BankAccountViewSet, basename="bankaccount")
router.register("contributions", ContributionViewSet, basename="contribution")
router.register("expenses", ExpenseViewSet, basename="expense")

urlpatterns = [
    path("transparency/", TransparencyView.as_view(), name="transparency"),
    *router.urls,
]
