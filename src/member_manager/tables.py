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

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole

from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import MEMBER_REMOVED
from openstack_auth_shib.notifications import MEMBER_REMOVED_ADM
from openstack_auth_shib.notifications import CHANGED_MEMBER_ROLE
from openstack_auth_shib.utils import TENANTADMIN_ROLE
from openstack_auth_shib.utils import get_admin_roleid

LOG = logging.getLogger(__name__)
DEFAULT_ROLE = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', '')

class DeleteMemberAction(tables.DeleteAction):
    data_type_singular = _("Member")
    data_type_plural = _("Members")

    def allowed(self, request, datum):
        return not datum.is_t_admin
    
    def delete(self, request, obj_id):
    
        try:
            
            with transaction.atomic():
                roles_obj = client_factory(request).roles
                role_assign_obj = client_factory(request).role_assignments
                
                arg_dict = {
                    'project' : request.user.tenant_id,
                    'user' : obj_id
                }
                for r_item in role_assign_obj.list(**arg_dict):
                    roles_obj.revoke(r_item.role['id'], **arg_dict)

                PrjRole.objects.filter(
                    registration__userid=obj_id,
                    project__projectname=request.user.tenant_name
                ).delete()
            
            tmpres = EMail.objects.filter(registration__userid=obj_id)
            member_email = tmpres[0].email if tmpres else None
            member_name = tmpres[0].registration.username if tmpres else None
            
            tmpres = EMail.objects.filter(registration__userid=request.user.id)
            admin_email = tmpres[0].email if tmpres else None

            noti_params = {
                'username' : member_name,
                'admin_address' : admin_email,
                'project' : request.user.tenant_name
            }
            notifyUser(request=request, rcpt=member_email, action=MEMBER_REMOVED, context=noti_params,
                       dst_user_id=obj_id)
            notifyAdmin(request=request, action=MEMBER_REMOVED_ADM, context=noti_params)

            
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
                    t_role_id = get_admin_roleid(request)
            
            roles_obj = client_factory(request).roles
            arg_dict = {
                'project' : request.user.tenant_id,
                'user' : obj_id
            }
            
            tmpres = EMail.objects.filter(registration__userid=obj_id)
            member_email = tmpres[0].email if tmpres else None

            tmpres = EMail.objects.filter(registration__userid=request.user.id)
            admin_email = tmpres[0].email if tmpres else None

            datum = data_table.get_object_by_id(obj_id)
            if datum.is_t_admin:

                with transaction.atomic():

                    PrjRole.objects.filter(
                        registration__userid=obj_id,
                        project__projectname=request.user.tenant_name
                    ).delete()

                    if datum.num_of_roles == 1:
                        missing_default = True
                        for item in roles_obj.list():
                            if item.name == DEFAULT_ROLE:
                                roles_obj.grant(item.id, **arg_dict)
                                missing_default = False
                        if missing_default:
                            raise Exception('Cannot swith to member role')

                    roles_obj.revoke(t_role_id, **arg_dict)

                noti_params = {
                    'admin_address' : admin_email,
                    'project' : request.user.tenant_name,
                    's_role' : _('Project manager'),
                    'd_role' : _('Project user')
                }
                notifyUser(request=request, rcpt=member_email, action=CHANGED_MEMBER_ROLE, context=noti_params,
                           dst_project_id=request.user.project_id, dst_user_id=obj_id)
            
            else:

                with transaction.atomic():

                    prjRole = PrjRole()
                    prjRole.registration = Registration.objects.filter(userid=obj_id)[0]
                    prjRole.project = Project.objects.get(projectname=request.user.tenant_name)
                    prjRole.roleid = t_role_id
                    prjRole.save()

                    roles_obj.grant(t_role_id, **arg_dict)

                noti_params = {
                    'admin_address' : admin_email,
                    'project' : request.user.tenant_name,
                    's_role' : _('Project user'),
                    'd_role' : _('Project manager')
                }
                notifyUser(request=request, rcpt=member_email, action=CHANGED_MEMBER_ROLE, context=noti_params,
                           dst_project_id=request.user.project_id, dst_user_id=obj_id)

        except:
            LOG.error("Toggle role error", exc_info=True)
            messages.error(request, _('Unable to toggle the role.'))
           
        if obj_id == request.user.id:
            response = shortcuts.redirect(reverse_lazy('logout'))
            msg = _("Roles changed. Please log in again to continue.")
            utils.add_logout_reason(request, response, msg)
            return response
            
        return shortcuts.redirect(reverse_lazy('horizon:idmanager:member_manager:index'))

class ChangeExpAction(tables.LinkAction):
    name = "change_expiration"
    verbose_name = _("Change Expiration")
    url = "horizon:idmanager:member_manager:modifyexp"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return not datum.is_t_admin

def get_role(data):
    if data.is_t_admin:
        return _('Project manager')
    else:
        return _('Project user')

class MemberTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    #userid = tables.Column('userid', verbose_name=_('User ID'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    organization = tables.Column('organization', verbose_name=_('Organization'))
    expiration = tables.Column('expiration', verbose_name=_('Expiration date'))
    role = tables.Column(get_role, verbose_name=_('Role'))
    
    class Meta:
        name = "member_table"
        verbose_name = _("Project members")
        row_actions = (ToggleRoleAction, ChangeExpAction, DeleteMemberAction,)
        table_actions = ()

    def get_object_id(self, datum):
        return datum.userid





