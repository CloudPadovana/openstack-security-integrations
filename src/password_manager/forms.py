#from django.conf import settings
from django.forms import ValidationError
from django import http
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy
from django.views.decorators.debug import sensitive_variables

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import functions as utils
from horizon.utils import validators

from openstack_dashboard import api


class PasswordForm(forms.SelfHandlingForm):
    new_password = forms.RegexField(label=_("New password"),
               widget=forms.PasswordInput(render_value=False),
               regex=validators.password_validator(),
               error_messages={'invalid':
               validators.password_validator_msg()})
    confirm_password = forms.CharField(label=_("Confirm new password"),
                            widget=forms.PasswordInput(render_value=False))

    def clean(self):
        data = super(forms.Form, self).clean()
        if 'new_password' in data:
            if data['new_password'] != data.get('confirm_password', None):
                raise ValidationError(_('Passwords do not match.'))
        return data

    @sensitive_variables('data')
    def handle(self, request, data):

        user_is_editable = api.keystone.keystone_can_edit_user()
        if not user_is_editable:
            messages.error(request, _('Activating password is not supported.'))
            return False

        try:
            api.keystone.user_update_own_password(request, None, data['new_password'])
            
            if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-shib'):
                #
                # TODO verify workaround
                #
                return http.HttpResponseRedirect(reverse_lazy('login'))
            else:
                response = http.HttpResponseRedirect(reverse_lazy('logout'))
                msg = _("Password changed. Please log in again to continue.")
                utils.add_logout_reason(request, response, msg)
                return response
                
        except Exception:
            exceptions.handle(request, _('Unable to activate password.'))

        return False

