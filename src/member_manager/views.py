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

class IndexView(tables.DataTableView):
    table_class = MemberTable
    template_name = 'project/member_manager/member_manager.html'

    def get_data(self):
    
        try:
        
            all_roles = client_factory(self.request).role_assignments.list(project=self.request.user.tenant_id)
            member_id_set = set()
            for r_item in all_roles:
                member_id_set.add(r_item.user['id'])
        
            return Registration.objects.filter(userid__in=member_id_set)
        
        except Exception:
            LOG.error("Member view error", exc_info=True)
            messages.error(self.request, _('Unable to retrieve member list.'))

        return list()


