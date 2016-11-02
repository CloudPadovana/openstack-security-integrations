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

from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.notifications import notification_render
from openstack_auth_shib.notifications import notify as notifyUsers
from openstack_auth_shib.notifications import SUBSCR_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_NO_TYPE
from openstack_auth_shib.utils import TENANTADMIN_ROLE

from openstack_dashboard.api.keystone import keystoneclient as client_factory

from django.utils.translation import ugettext as _

LOG = logging.getLogger(__name__)

class ApproveSubscrForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ApproveSubscrForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.CharField(widget=HiddenInput)
        self.fields['username'] = forms.CharField(widget=HiddenInput)
        self.fields['action'] = forms.CharField(widget=HiddenInput)

        if kwargs['initial']['action'] == 'reject':
            self.fields['reason'] = forms.CharField(
                label=_('Message'),
                required=False,
                widget=forms.widgets.Textarea()
            )

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
        
            role_names = [ role['name'] for role in self.request.user.roles ]
            if not TENANTADMIN_ROLE in role_names:
                raise Exception(_('Permissions denied: cannot approve subscriptions'))
        
            with transaction.atomic():
            
                LOG.debug("Approving subscription for %s" % data['username'])
                
                curr_prjname = self.request.user.tenant_name
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectname' : curr_prjname
                }                
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                
                member = client_factory(request).users.get(prj_req.registration.userid)
                project_name = prj_req.project.projectname
                
                if data['action'] == 'accept':
                    default_role = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', None)

                    roles_obj = client_factory(request).roles
                    arg_dict = {
                        'project' : prj_req.project.projectid,
                        'user' : prj_req.registration.userid
                    }
                    
                    missing_default = True
                    for item in roles_obj.list():
                        if item.name == default_role:
                            roles_obj.grant(item.id, **arg_dict)
                            missing_default = False
                    if missing_default:
                        raise Exception("Default role is undefined")
                    
                #
                # clear request
                #
                prj_req.delete()

            #
            # send notification to the user
            #
            noti_params = {
                'project' : project_name
            }
            if data['action'] == 'accept':
                tpl_type = SUBSCR_OK_TYPE
            else:
                tpl_type = SUBSCR_NO_TYPE

            noti_sbj, noti_body = notification_render(tpl_type, noti_params)
            notifyUsers(member.email, noti_sbj, noti_body)
        
        except:
            exceptions.handle(request)
            return False
            
        return True



