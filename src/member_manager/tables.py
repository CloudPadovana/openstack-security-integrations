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
from django.urls import reverse_lazy as reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy

from horizon import tables
from horizon import messages
#from horizon.utils import functions as horizon_utils

# TODO use keystone api wrappers
from openstack_dashboard.api.keystone import keystoneclient as client_factory

from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import PSTATUS_RENEW_DISC

from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import MEMBER_REMOVED
from openstack_auth_shib.notifications import MEMBER_REMOVED_ADM

LOG = logging.getLogger(__name__)

class DeleteMemberAction(tables.DeleteAction):
    data_type_singular = _("Member")
    data_type_plural = _("Members")

    @staticmethod
    def action_present(count):
        return ngettext_lazy(
            "Delete Member",
            "Delete Members",
            count
        )

    @staticmethod
    def action_past(count):
        return ngettext_lazy(
            "Deleted Member",
            "Deleted Members",
            count
        )

    def allowed(self, request, datum):
        return not datum.is_t_admin
    
    def delete(self, request, obj_id):
    
        try:
            
            with transaction.atomic():

                q_args = {
                    'registration__userid' : obj_id,
                    'project__projectname' : request.user.tenant_name
                }
                Expiration.objects.delete_expiration(**q_args)
                PrjRequest.objects.filter(**q_args).delete()
                PrjRole.objects.filter(**q_args).delete()

                roles_obj = client_factory(request).roles
                role_assign_obj = client_factory(request).role_assignments
                
                arg_dict = {
                    'project' : request.user.tenant_id,
                    'user' : obj_id
                }
                for r_item in role_assign_obj.list(**arg_dict):
                    roles_obj.revoke(r_item.role['id'], **arg_dict)

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

class ProposeAdminAction(tables.LinkAction):
    name = "proposeadminlink"
    verbose_name = _("Propose admin")
    url = "horizon:idmanager:member_manager:proposeadmin"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return not datum.is_t_admin

class DemoteUserAction(tables.LinkAction):
    name = "demote_user"
    verbose_name = _("Demote user")
    url = "horizon:idmanager:member_manager:demote"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return datum.is_t_admin and datum.num_of_admins > 1

class ChangeExpAction(tables.LinkAction):
    name = "change_expiration"
    verbose_name = _("Change Expiration")
    url = "horizon:idmanager:member_manager:modifyexp"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return not datum.is_t_admin

class SendMessageAction(tables.LinkAction):
    name = "send_message"
    verbose_name = _("Send Message")
    url = "horizon:idmanager:member_manager:sendmsg"
    classes = ("ajax-modal", "btn-edit")

def get_role(data):
    if data.is_t_admin:
        return _('Project manager')
    else:
        return _('Project user')

class MemberTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    #userid = tables.Column('userid', verbose_name=_('User ID'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    organization = tables.Column('organization', verbose_name=_('Home institution'))
    expiration = tables.Column('expiration', verbose_name=_('Expiration date'))
    role = tables.Column(get_role, verbose_name=_('Role'))
    
    class Meta:
        name = "member_table"
        verbose_name = _("Project members")
        row_actions = (
            ProposeAdminAction,
            DemoteUserAction,
            ChangeExpAction,
            DeleteMemberAction,)
        table_actions = (SendMessageAction,)

    def get_object_id(self, datum):
        return datum.userid





