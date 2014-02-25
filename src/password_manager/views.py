from horizon import forms

from django.core.urlresolvers import reverse_lazy

from .forms import PasswordForm

class PasswordView(forms.ModalFormView):
    form_class = PasswordForm
    template_name = 'settings/password_manager/activate.html'
    success_url = reverse_lazy('logout')

