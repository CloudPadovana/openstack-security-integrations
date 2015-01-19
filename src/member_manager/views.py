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

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy

from horizon import tables
from horizon import messages
from horizon import forms

from openstack_dashboard.api.keystone import keystoneclient as client_factory
from openstack_auth_shib.models import Registration

from .tables import MemberTable

LOG = logging.getLogger(__name__)

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')

class MemberItem():

    def __init__(self, registration, is_t_admin):
        self.username = registration.username
        self.userid = registration.userid
        self.givenname = registration.givenname
        self.sn = registration.sn
        self.organization = registration.organization
        self.role = _("Admin") if is_t_admin else _("User")

class IndexView(tables.DataTableView):
    table_class = MemberTable
    template_name = 'project/member_manager/member_manager.html'

    def get_data(self):
    
        try:
            t_role_id = ''
            for role in self.request.user.roles:
                if role['name'] == TENANTADMIN_ROLE:
                    t_role_id = role['id']
        
            role_assign_obj = client_factory(self.request).role_assignments
            member_id_dict = dict()
            for r_item in role_assign_obj.list(project=self.request.user.tenant_id):
                if r_item.role['id'] == t_role_id:
                    member_id_dict[r_item.user['id']] = True
                elif not r_item.user['id'] in member_id_dict:
                    member_id_dict[r_item.user['id']] = False
        
            all_regs = Registration.objects.filter(userid__in=member_id_dict)
            return [ MemberItem(reg, member_id_dict[reg.userid]) for reg in all_regs ]
        
        except Exception:
            LOG.error("Member view error", exc_info=True)
            messages.error(self.request, _('Unable to retrieve member list.'))

        return list()


