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

from django.db import transaction
from django.utils.translation import ugettext as _

from horizon import tables

from openstack_dashboard.dashboards.identity.users.tables import UsersTable as BaseUsersTable
from openstack_dashboard.dashboards.identity.users.tables import EditUserLink as BaseEditUserLink
from openstack_dashboard.dashboards.identity.users.tables import ToggleEnabled
from openstack_dashboard.dashboards.identity.users.tables import DeleteUsersAction as BaseDeleteUsersAction
from openstack_dashboard.dashboards.identity.users.tables import UserFilterAction

from openstack_auth_shib.models import Registration
from openstack_auth_shib.utils import get_project_managers

from openstack_dashboard.api import keystone as keystone_api

from keystoneclient.exceptions import AuthorizationFailure

LOG = logging.getLogger(__name__)

class EditUserLink(BaseEditUserLink):
    url = "horizon:idmanager:user_manager:update"

class DeleteUsersAction(BaseDeleteUsersAction):

    def delete(self, request, obj_id):
    
        tenant_ref = None
        tenants, dummy = keystone_api.tenant_list(request, user=obj_id)
        
        for tmpten in tenants:
            tenant_managers = get_project_managers(request, tmpten.id)
            if len(tenant_managers) == 1 and tenant_managers[0].id == obj_id:
                tenant_ref = tmpten.name
        
        if tenant_ref:
            
            failure = AuthorizationFailure()
            failure._safe_message=_("Cannot delete unique admin for %s") % tenant_ref
            raise failure
        
        else:

            with transaction.atomic():
                Registration.objects.filter(userid=obj_id).delete()
                super(DeleteUsersAction, self).delete(request, obj_id)
        
class RenewLink(tables.LinkAction):
    name = "renewexp"
    verbose_name = _("Renew Expiration")
    url = "horizon:idmanager:user_manager:renew"
    classes = ("ajax-modal", "btn-edit")

class UsersTable(BaseUsersTable):

    expiration = tables.Column('expiration', verbose_name=_('Expiration date'))

    class Meta:
        name = "user_table"
        verbose_name = _("Users")
        row_actions = (
            EditUserLink,
            ToggleEnabled,
            RenewLink,
            DeleteUsersAction
        )
        table_actions = (UserFilterAction, DeleteUsersAction)

