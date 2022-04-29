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
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy as reverse

from horizon import tables
from horizon import messages
from horizon import forms

from openstack_dashboard.api.keystone import keystoneclient as client_factory
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.utils import TENANTADMIN_ROLE
from openstack_auth_shib.utils import get_admin_roleid

from .tables import MemberTable
from .forms import ModifyExpForm
from .forms import SendMsgForm

LOG = logging.getLogger(__name__)

class MemberItem():

    def __init__(self, registration, role_params, exp_date):
        self.username = registration.username
        self.userid = registration.userid
        self.fullname = registration.givenname + " " + registration.sn
        self.organization = registration.organization
        self.expiration = exp_date
        self.is_t_admin = role_params[0]
        self.num_of_roles = role_params[1]
        self.num_of_admins = role_params[2]

class IndexView(tables.DataTableView):
    table_class = MemberTable
    template_name = 'idmanager/member_manager/member_manager.html'
    page_title = _("Project Members")

    def get_data(self):
    
        try:
            t_role_id = ''
            for role in self.request.user.roles:
                if role['name'] == TENANTADMIN_ROLE:
                    t_role_id = get_admin_roleid(self.request)
        
            role_assign_obj = client_factory(self.request).role_assignments
            member_id_dict = dict()
            number_of_admins = 0
            for r_item in role_assign_obj.list(project=self.request.user.tenant_id):
                if not r_item.user['id'] in member_id_dict:
                    member_id_dict[r_item.user['id']] = [False, 0, 0]
                    
                if r_item.role['id'] == t_role_id:
                    member_id_dict[r_item.user['id']][0] = True
                    number_of_admins +=1
                    
                member_id_dict[r_item.user['id']][1] += 1
            
            for rp_item in member_id_dict.values():
                rp_item[2] = number_of_admins
        
            result = list()
            q_args = {
                'registration__userid__in' : member_id_dict,
                'project__projectid' : self.request.user.tenant_id
            }
            for expir in Expiration.objects.filter(**q_args):
                reg = expir.registration
                result.append(MemberItem(reg, member_id_dict[reg.userid], expir.expdate))
            return result
        
        except Exception:
            LOG.error("Member view error", exc_info=True)
            messages.error(self.request, _('Unable to retrieve member list.'))

        return list()

class ModifyExpView(forms.ModalFormView):
    form_class = ModifyExpForm
    template_name = 'idmanager/member_manager/modifyexp.html'
    success_url = reverse('horizon:idmanager:member_manager:index')

    def get_context_data(self, **kwargs):
        context = super(ModifyExpView, self).get_context_data(**kwargs)
        context['userid'] = self.get_object()
        return context

    def get_initial(self):
        return {
            'userid' : self.get_object(),
            'expiration' : datetime.now(timezone.utc) + timedelta(365)
        }

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['userid']
        return self._object

class SendMsgView(forms.ModalFormView):
    form_class = SendMsgForm
    template_name = 'idmanager/member_manager/sendmsg.html'
    success_url = reverse('horizon:idmanager:member_manager:index')


