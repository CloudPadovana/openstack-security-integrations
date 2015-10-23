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
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.http import urlencode

from horizon import tables
from horizon import forms
from horizon import messages

from openstack_dashboard.dashboards.identity.projects import tables as baseTables

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_PRIVATE, PRJ_PUBLIC, PRJ_GUEST

LOG = logging.getLogger(__name__)

class UpdateMembersLink(baseTables.UpdateMembersLink):
    url = "horizon:idmanager:project_manager:update"

class UpdateGroupsLink(baseTables.UpdateGroupsLink):
    url = "horizon:idmanager:project_manager:update"
    
class UpdateProject(baseTables.UpdateProject):
    url = "horizon:idmanager:project_manager:update"

class UsageLink(baseTables.UsageLink):
    url = "horizon:idmanager:project_manager:usage"
    
class ModifyQuotas(baseTables.ModifyQuotas):
    url = "horizon:idmanager:project_manager:update"

class CreateProject(baseTables.CreateProject):
    url = "horizon:idmanager:project_manager:create"

class DeleteProjectAction(baseTables.DeleteTenantsAction):

    def delete(self, request, obj_id):
    
        with transaction.atomic():
            Project.objects.filter(projectid=obj_id).delete()
            super(DeleteProjectAction, self).delete(request, obj_id)

class RescopeTokenToProject(baseTables.RescopeTokenToProject):

    def get_link_url(self, project):
        # redirects to the switch_tenants url which then will redirect
        # back to this page
        dash_url = reverse("horizon:idmanager:project_manager:index")
        base_url = reverse(self.url, args=[project.id])
        param = urlencode({"next": dash_url})
        return "?".join([base_url, param])

class ToggleVisibility(tables.Action):
    name = "toggle_visible"
    verbose_name = _("Toggle Visibility")
    policy_rules = (('identity', 'identity:update_project'),)
    
    def single(self, data_table, request, object_id):
    
        with transaction.atomic():
        
            prj_list = Project.objects.filter(projectid=object_id)
            if len(prj_list):
                prj_status = int(prj_list[0].status)
                if prj_status is PRJ_PRIVATE:
                    prj_list[0].status = PRJ_PUBLIC
                    prj_list[0].save()
                elif prj_status is PRJ_PUBLIC:
                    prj_list[0].status = PRJ_PRIVATE
                    prj_list[0].save()
                elif prj_status is PRJ_GUEST:
                    messages.error(request, _("Cannot toggle guest project"))
            
        return shortcuts.redirect(reverse('horizon:idmanager:project_manager:index'))

class ReqProjectLink(tables.LinkAction):
    name = "reqproject"
    verbose_name = _("Subscribe to project")
    url = "horizon:idmanager:project_requests:index"
    classes = ("ajax-modal", "btn-edit")

def get_prj_status(data):
    if data.status == PRJ_GUEST:
        return _("Guest")
    elif data.status == PRJ_PUBLIC:
        return _("Public")
    return _("Private")

class ProjectsTable(baseTables.TenantsTable):
    status = tables.Column(get_prj_status, verbose_name=_('Status'), status=True)

    class Meta:
        name = "projects"
        verbose_name = _("Projects")
        row_actions = (UpdateMembersLink,
                       UpdateGroupsLink,
                       UpdateProject,
                       UsageLink,
                       ModifyQuotas,
                       ToggleVisibility,
                       DeleteProjectAction,
                       RescopeTokenToProject)
        table_actions = (baseTables.TenantFilterAction, 
                         CreateProject,
                         ReqProjectLink,
                         DeleteProjectAction)
        pagination_param = "tenant_marker"


