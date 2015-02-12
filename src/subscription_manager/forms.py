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

from horizon import forms
from horizon import exceptions

from django.db import transaction
from django.conf import settings
from django.forms.widgets import HiddenInput
from django.views.decorators.debug import sensitive_variables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PSTATUS_APPR
from openstack_auth_shib.models import PSTATUS_REJ

from openstack_auth_shib.notifications import notification_render
from openstack_auth_shib.notifications import notifyManagers
from openstack_auth_shib.notifications import SUBSCR_CHKD_TYPE

from django.utils.translation import ugettext as _

LOG = logging.getLogger(__name__)
TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')

class ApproveSubscrForm(forms.SelfHandlingForm):

    #readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
    
    regid = forms.IntegerField(label=_("ID"), widget=HiddenInput)
    username = forms.CharField(label=_("User name"), widget=HiddenInput)
    givenname = forms.CharField(label=_("First name"), widget=HiddenInput)
    sn = forms.CharField(label=_("Last name"), widget=HiddenInput)
    notes = forms.CharField(label=_("Notes"), required=False, widget=HiddenInput)
    checkaction = forms.CharField(widget=HiddenInput, initial='accept')

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
        
            role_names = [ role['name'] for role in self.request.user.roles ]
            if not TENANTADMIN_ROLE in role_names:
                raise Exception(_('Permissions denied: cannot approve subscriptions'))
        
            with transaction.commit_on_success():
            
                LOG.debug("Approving subscription for %s" % data['username'])
                
                curr_prjname = self.request.user.tenant_name
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectname' : curr_prjname
                }
                
                if data['checkaction'] == 'accept':
                    new_status = PSTATUS_APPR
                else:
                    new_status = PSTATUS_REJ
                    
                PrjRequest.objects.filter(**q_args).update(flowstatus=new_status)
            
                noti_params = {
                    'username' : data['username'],
                    'project' : curr_prjname
                }
                noti_sbj, noti_body = notification_render(SUBSCR_CHKD_TYPE, noti_params)
                notifyManagers(noti_sbj, noti_body)
        
        except:
            exceptions.handle(request)
            return False
            
        return True



