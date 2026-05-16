"""Server-rendered URLs for the members app (officer console)."""
from django.urls import path

from apps.members.web_views import MemberListView

app_name = 'members'

urlpatterns = [
    path('', MemberListView.as_view(), name='list'),
]
