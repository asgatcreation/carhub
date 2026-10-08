from allauth.account.views import PasswordResetView
from allauth.socialaccount.models import SocialAccount


class CarHubPasswordResetView(PasswordResetView):
    """Forgot password, aware of accounts created with Google.

    If the email belongs to an account that has never had a password (it signs in with Google),
    don't fire off a code straight away: offer "Continue with Google", or a code to add a password
    to the same account. Accounts with a password get the normal code flow.
    """

    def form_valid(self, form):
        users = getattr(form, 'users', [])
        google_only = users and all(not u.has_usable_password() for u in users)
        if google_only and not self.request.POST.get('add_password'):
            via_google = SocialAccount.objects.filter(user__in=users, provider='google').exists()
            return self.render_to_response(self.get_context_data(
                form=form, google_choice=form.cleaned_data['email'], via_google=via_google))
        return super().form_valid(form)
