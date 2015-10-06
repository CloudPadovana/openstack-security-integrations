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

from django import shortcuts
from django.db import transaction
from django.conf import settings
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

from horizon import tables
from horizon import messages
from horizon.utils import functions as utils

from openstack_dashboard.api.keystone import keystoneclient as client_factory

LOG = logging.getLogger(__name__)
TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
DEFAULT_ROLE = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', '')

class DeleteMemberAction(tables.DeleteAction):
    data_type_singular = _("Member")
    data_type_plural = _("Members")

    def allowed(self, request, datum):
        return not datum.is_t_admin
    
    def delete(self, request, obj_id):
    
        try:
            
            roles_obj = client_factory(request).roles
            role_assign_obj = client_factory(request).role_assignments
            
            arg_dict = {
                'project' : request.user.tenant_id,
                'user' : obj_id
            }
            for r_item in role_assign_obj.list(**arg_dict):
                roles_obj.revoke(r_item.role['id'], **arg_dict)
            
        except:
            LOG.error("Grant revoke error", exc_info=True)
            messages.error(request, _('Unable to delete member from tenant.'))

class ToggleRoleAction(tables.Action):
    name = "toggle_role"
    verbose_name = _("Toggle Role")
    
    def allowed(self, request, datum):
        return not (datum.is_t_admin and datum.num_of_admins == 1)

    def single(self, data_table, request, obj_id):
        
        try:
        
            t_role_id = ''
            for role in request.user.roles:
                if role['name'] == TENANTADMIN_ROLE:
                    t_role_id = role['id']
            
            roles_obj = client_factory(request).roles
            arg_dict = {
                'project' : request.user.tenant_id,
                'user' : obj_id
            }
                        
            datum = data_table.get_object_by_id(obj_id)
            if datum.is_t_admin:
            
                if datum.num_of_roles == 1:
                    missing_default = True
                    for item in roles_obj.list():
                        if item.name == DEFAULT_ROLE:
                            roles_obj.grant(item.id, **arg_dict)
                            missing_default = False
                    if missing_default:
                        raise Exception('Cannot swith to member role')
                        
                roles_obj.revoke(t_role_id, **arg_dict)
            else:
                roles_obj.grant(t_role_id, **arg_dict)

        except:
            LOG.error("Toggle role error", exc_info=True)
            messages.error(request, _('Unable to toggle the role.'))
           
        if obj_id == request.user.id:
            response = shortcuts.redirect(reverse_lazy('logout'))
            msg = _("Roles changed. Please log in again to continue.")
            utils.add_logout_reason(request, response, msg)
            return response
            
        return shortcuts.redirect(reverse_lazy('horizon:identity:member_manager:index'))

def get_role(data):
    if data.is_t_admin:
        return _('Admin')
    else:
        return _('User')

class MemberTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    userid = tables.Column('userid', verbose_name=_('User ID'))
    givenname = tables.Column('givenname', verbose_name=_('First name'))
    sn = tables.Column('sn', verbose_name=_('Last name'))
    organization = tables.Column('organization', verbose_name=_('Organization'))
    role = tables.Column(get_role, verbose_name=_('Role'))
    
    class Meta:
        name = "member_table"
        verbose_name = _("Project members")
        row_actions = (ToggleRoleAction, DeleteMemberAction,)
        table_actions = ()

    def get_object_id(self, datum):
        return datum.userid





