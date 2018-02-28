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

from django.core.urlresolvers import reverse
from django.db import transaction
from django.utils.translation import ugettext as _

from horizon import tables

from openstack_dashboard.dashboards.identity.users import tables as baseTables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import USER_PURGED_TYPE
from openstack_auth_shib.utils import get_project_managers

from openstack_dashboard.api import keystone as keystone_api

from horizon import messages

LOG = logging.getLogger(__name__)

class EditUserLink(baseTables.EditUserLink):
    url = "horizon:idmanager:user_manager:update"

class ChangePasswordLink(baseTables.ChangePasswordLink):
    url = "horizon:idmanager:user_manager:change_password"
    
class DeleteUsersAction(baseTables.DeleteUsersAction):

    def delete(self, request, obj_id):
    
        tenant_ref = None
        tenants, dummy = keystone_api.tenant_list(request, user=obj_id)
        
        for tmpten in tenants:
            tenant_managers = get_project_managers(request, tmpten.id)
            if len(tenant_managers) == 1 and tenant_managers[0].id == obj_id:
                tenant_ref = tmpten.name
        
        if tenant_ref:
            
            msg = _("User is the unique admin for %s") % tenant_ref
            messages.error(request, msg)
            raise Exception(msg)
        
        else:
            tmpres = EMail.objects.filter(registration__userid=obj_id)
            user_email = tmpres[0].email if tmpres else None
            user_name = tmpres[0].registration.username if tmpres else None

            with transaction.atomic():
                Registration.objects.filter(userid=obj_id).delete()
                super(DeleteUsersAction, self).delete(request, obj_id)

            noti_params = {
                'username' : user_name
            }
            notifyUser(request=request, rcpt=user_email, action=USER_PURGED_TYPE,
                       context=noti_params, dst_user_id=obj_id)

            #
            # TODO send notification to prj admins (if available)
            #

class RenewLink(tables.LinkAction):
    name = "renewexp"
    verbose_name = _("Renew Expiration")
    url = "horizon:idmanager:user_manager:renew"
    classes = ("ajax-modal", "btn-edit")

class CheckOrphanLink(tables.LinkAction):
    name = "checkorphan"
    verbose_name = _("Orphan users")
    url = "horizon:idmanager:user_manager:checkorphans"

class UsersTable(baseTables.UsersTable):

    # patch for user detail and ajax update disabled
    def __init__(self, request, data=None, needs_form_wrapper=None, **kwargs):
        super(UsersTable, self).__init__(request, data=data,
                                         needs_form_wrapper=needs_form_wrapper, **kwargs)
        
        self.columns['name'].get_link_url = self._get_detail_link
        self.columns['name'].update_action = None
        if 'description' in self.columns:
            self.columns['description'].update_action = None
        if 'email' in self.columns:
            self.columns['email'].update_action = None

    def _get_detail_link(self, user):
        return reverse("horizon:idmanager:user_manager:detail", args=(user.id,))
    # end of patch
    
    class Meta:
        name = "user_table"
        verbose_name = _("Users")
        row_actions = (
            EditUserLink,
            ChangePasswordLink,
            baseTables.ToggleEnabled,
            RenewLink,
            DeleteUsersAction
        )
        table_actions = (
            baseTables.UserFilterAction,
            CheckOrphanLink,
            DeleteUsersAction
        )

class CloseOrphanLink(tables.LinkAction):
    name = "closeorphan"
    verbose_name = _("Active users")
    url = "horizon:idmanager:user_manager:index"

class OrphanTable(tables.DataTable):
    name = tables.Column('name', verbose_name=_('User name'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    expdate = tables.Column('expdate', verbose_name=_('Expiration Date'))

    class Meta:
        name = "orphan_table"
        verbose_name = _("Orphans")
        row_actions = (DeleteUsersAction,)
        table_actions = (CloseOrphanLink,)

    def get_object_id(self, datum):
        return datum.id

