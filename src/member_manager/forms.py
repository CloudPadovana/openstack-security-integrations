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

import logging

from datetime import datetime

from django.db import transaction
from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.forms.extras.widgets import SelectDateWidget
from django.utils.translation import ugettext as _
from django.views.decorators.debug import sensitive_variables

from horizon import forms
from horizon import exceptions

from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import USER_RENEWED_TYPE

LOG = logging.getLogger(__name__)

try:
    MAX_RENEW = int(getattr(settings, 'TENANT_MAX_RENEW', '4'))
except:
    MAX_RENEW = 4

class ModifyExpForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ModifyExpForm, self).__init__(request, *args, **kwargs)

        self.fields['userid'] = forms.CharField(widget=HiddenInput)
        
        curr_year = datetime.utcnow().year
        years_list = range(curr_year, curr_year + MAX_RENEW)           
        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            required=True,
            widget=SelectDateWidget(None, years_list)
        )

    def clean(self):
        data = super(ModifyExpForm, self).clean()

        now = datetime.utcnow()
        if data['expiration'].date() < now.date():
            raise ValidationError(_('Invalid expiration time.'))
        if data['expiration'].year > now.year + MAX_RENEW:
            raise ValidationError(_('Invalid expiration time.'))

        if data['userid'] == self.request.user.id:
            raise ValidationError(_('Invalid operation.'))
        #
        # TODO cannot change expdate for tenant admin
        #

        return data

    @sensitive_variables('data')
    def handle(self, request, data):
        try:
            
            with transaction.atomic():
                
                q_args = {
                    'registration__userid' : data['userid'],
                    'project__projectid' : request.user.tenant_id
                }
                Expiration.objects.filter(**q_args).update(expdate=data['expiration'])
                
            tmpres = EMail.objects.filter(registration__userid=data['userid'])
            if len(tmpres):
                mail_obj = tmpres[0]
                noti_params = {
                    'username' : mail_obj.registration.username,
                    'expiration' : data['expiration'].strftime("%d %B %Y")
                }
                notifyUser(request=request, rcpt=mail_obj.email, action=USER_RENEWED_TYPE,
                           context=noti_params, dst_user_id=data['userid'])
                notifyAdmin(request=request, action=USER_RENEWED_TYPE, context=noti_params)

        except:
            exceptions.handle(request)
            return False
        return True





