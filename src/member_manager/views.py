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
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy as reverse

from horizon import tables
from horizon import messages
from horizon import forms

from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PrjAttribute

from openstack_auth_shib.utils import get_prj_expiration

from .tables import MemberTable
from .forms import ModifyExpForm
from .forms import DemoteUserForm
from .forms import ProposeAdminForm
from .forms import SendMsgForm

LOG = logging.getLogger(__name__)

class MemberItem():

    def __init__(self, registration, exp_date, is_adm, n_adm):
        self.username = registration.username
        self.userid = registration.userid
        self.fullname = registration.givenname + " " + registration.sn
        self.organization = registration.organization
        self.expiration = exp_date
        self.is_t_admin = is_adm
        self.num_of_admins = n_adm

class IndexView(tables.DataTableView):
    table_class = MemberTable
    template_name = 'idmanager/member_manager/member_manager.html'
    page_title = _("Project Members")

    def get_data(self):
    
        result = list()

        try:
            with transaction.atomic():

                admin_set = set()
                for item in PrjRole.objects.filter(project__projectid = self.request.user.tenant_id):
                    admin_set.add(item.registration.userid)

                for item in Expiration.objects.filter(project__projectid = self.request.user.tenant_id):
                    m_item = MemberItem(item.registration,
                                        item.expdate,
                                        item.registration.userid in admin_set,
                                        len(admin_set))
                    result.append(m_item)

        except Exception:
            LOG.error("Member view error", exc_info=True)
            messages.error(self.request, _('Unable to retrieve member list.'))

        return result

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
            'expiration' : get_prj_expiration(self.request)
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


