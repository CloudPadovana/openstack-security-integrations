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
from openstack_auth_shib.utils import TENANTADMIN_ROLEID

from .tables import MemberTable
from .forms import ModifyExpForm
from .forms import DemoteUserForm
from .forms import ProposeAdminForm
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
            role_assign_obj = client_factory(self.request).role_assignments
            member_id_dict = dict()
            number_of_admins = 0
            for r_item in role_assign_obj.list(project=self.request.user.tenant_id):
                if not r_item.user['id'] in member_id_dict:
                    member_id_dict[r_item.user['id']] = [False, 0, 0]
                    
                if r_item.role['id'] == TENANTADMIN_ROLEID:
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

class DemoteUserView(forms.ModalFormView):
    form_class = DemoteUserForm
    template_name = 'idmanager/member_manager/generic_ack.html'
    success_url = reverse('horizon:idmanager:member_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['userid']
        return self._object

    def get_initial(self):
        return { 'userid' : self.kwargs['userid'] }

    def get_context_data(self, **kwargs):
        context = super(DemoteUserView, self).get_context_data(**kwargs)
        context['form_action'] = reverse("horizon:idmanager:member_manager:demote",
                                         args=(self.get_object(),))
        context['op_question'] = _('Do you confirm user demotion to normal member?')
        return context

class ProposeAdminView(forms.ModalFormView):
    form_class = ProposeAdminForm
    template_name = 'idmanager/member_manager/generic_ack.html'
    success_url = reverse('horizon:idmanager:member_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['userid']
        return self._object

    def get_initial(self):
        return { 'userid' : self.kwargs['userid'] }

    def get_context_data(self, **kwargs):
        context = super(ProposeAdminView, self).get_context_data(**kwargs)
        context['form_action'] = reverse("horizon:idmanager:member_manager:proposeadmin",
                                         args=(self.get_object(),))
        context['op_question'] = _('Send promotion request to the cloud administrators?')
        return context

class SendMsgView(forms.ModalFormView):
    form_class = SendMsgForm
    template_name = 'idmanager/member_manager/sendmsg.html'
    success_url = reverse('horizon:idmanager:member_manager:index')


