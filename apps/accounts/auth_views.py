"""Re-authentication view.

RecentAuthRequiredMixin / DisciplineAccessMixin redirect here with ?next=...
when a user is authorized in principle but their last strong auth is stale.
The user re-enters their password; on success we stamp last_strong_auth_at
and bounce them back to `next`.

This is intentionally password-only (not full logout/login) so the user
stays in their session — it's a step-up, not a re-login.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView


class ReauthForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
        label='Confirm your password',
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data['password']
        if authenticate(username=self.user.email, password=password) is None:
            raise forms.ValidationError('Incorrect password.')
        return password


class ReauthView(LoginRequiredMixin, FormView):
    template_name = 'accounts/reauth.html'
    form_class = ReauthForm
    success_url = reverse_lazy('/')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def _safe_next(self) -> str:
        nxt = self.request.GET.get('next') or self.request.POST.get('next') or '/'
        if url_has_allowed_host_and_scheme(
            nxt, allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return nxt
        return '/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['next'] = self._safe_next()
        return ctx

    def form_valid(self, form):
        user = self.request.user
        user.last_strong_auth_at = timezone.now()
        user.save(update_fields=['last_strong_auth_at'])
        return redirect(self._safe_next())
