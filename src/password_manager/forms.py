#  Copyright (c) 2014 INFN - "Istituto Nazionale di Fisica Nucleare" - Italy
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License. 

#from django.conf import settings
from django.forms import ValidationError
from django import http
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse_lazy as reverse
from django.views.decorators.debug import sensitive_variables

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import functions as utils
from horizon.utils import validators

from openstack_dashboard import api

from openstack_auth_shib.models import PWD_LEN

class PasswordForm(forms.SelfHandlingForm):
    new_password = forms.RegexField(
        label=_("New password"),
        max_length=PWD_LEN,
        widget=forms.PasswordInput(render_value=False),
        regex=validators.password_validator(),
        error_messages={'invalid': validators.password_validator_msg()}
    )
    confirm_password = forms.CharField(
        label=_("Confirm new password"),
        max_length=PWD_LEN,
        widget=forms.PasswordInput(render_value=False)
    )

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
            #api.keystone.user_update_own_password(request, None, data['new_password'])
            api.keystone.user_update_password(request, request.user.id, data['new_password'], False)
            
            response = http.HttpResponseRedirect(reverse('logout'))
            msg = _("Password changed. Please log in again to continue.")
            utils.add_logout_reason(request, response, msg)
            return response
                
        except Exception:
            exceptions.handle(request, _('Unable to activate password.'))

        return False

