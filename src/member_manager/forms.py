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
from django.forms.widgets import SelectDateWidget
from django.utils.translation import ugettext as _
from django.views.decorators.debug import sensitive_variables

from horizon import forms
from horizon import exceptions

from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import USER_RENEWED_TYPE

from openstack_auth_shib.utils import set_last_exp

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
        years_list = list(range(curr_year, curr_year + MAX_RENEW))           
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

        q_args = {
            'registration__userid' : data['userid'],
            'project__projectid' : self.request.user.tenant_id
        }
        if PrjRole.objects.filter(**q_args).count() > 0:
            raise ValidationError(_('Cannot change expiration for a project admin'))

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

                set_last_exp(data['userid'])

                PrjRequest.objects.filter(**q_args).delete()

                tmpres = EMail.objects.filter(registration__userid=data['userid'])
                if len(tmpres) == 0:
                    return True

                user_name = tmpres[0].registration.username
                user_mail = tmpres[0].email
                noti_params = {
                    'username' : user_name,
                    'project' : request.user.tenant_name,
                    'expiration' : data['expiration'].strftime("%d %B %Y")
                }

                try:
                    notifyUser(request=request, rcpt=user_mail, action=USER_RENEWED_TYPE,
                               context=noti_params, dst_user_id=data['userid'])
                    notifyAdmin(request=request, action=USER_RENEWED_TYPE, context=noti_params)
                except:
                    LOG.error("Cannot notify %s" % user_name, exc_info=True)

        except:
            exceptions.handle(request)
            return False
        return True





