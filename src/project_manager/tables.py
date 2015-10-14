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
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext as _

from horizon import tables
from horizon import messages

from openstack_dashboard.dashboards.identity.projects.tables import TenantsTable

from openstack_dashboard.dashboards.identity.projects.tables import UpdateMembersLink as BaseUpdateMembersLink
from openstack_dashboard.dashboards.identity.projects.tables import UpdateGroupsLink as BaseUpdateGroupsLink
from openstack_dashboard.dashboards.identity.projects.tables import UpdateProject as BaseUpdateProject
from openstack_dashboard.dashboards.identity.projects.tables import UsageLink as BaseUsageLink
from openstack_dashboard.dashboards.identity.projects.tables import ModifyQuotas as BaseModifyQuotas
from openstack_dashboard.dashboards.identity.projects.tables import RescopeTokenToProject as BaseRescopeTokenToProject
from openstack_dashboard.dashboards.identity.projects.tables import DeleteTenantsAction

from openstack_dashboard.dashboards.identity.projects.tables import TenantFilterAction
from openstack_dashboard.dashboards.identity.projects.tables import CreateProject as BaseCreateProject

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_PRIVATE, PRJ_PUBLIC, PRJ_GUEST

LOG = logging.getLogger(__name__)

class UpdateMembersLink(BaseUpdateMembersLink):
    url = "horizon:idmanager:project_manager:update"

class UpdateGroupsLink(BaseUpdateGroupsLink):
    url = "horizon:idmanager:project_manager:update"
    
class UpdateProject(BaseUpdateProject):
    url = "horizon:idmanager:project_manager:update"

class UsageLink(BaseUsageLink):
    url = "horizon:idmanager:project_manager:usage"
    
class ModifyQuotas(BaseModifyQuotas):
    url = "horizon:idmanager:project_manager:update"

class CreateProject(BaseCreateProject):
    url = "horizon:idmanager:project_manager:create"

class DeleteProjectAction(DeleteTenantsAction):

    def delete(self, request, obj_id):
    
        with transaction.atomic():
            Project.objects.filter(projectid=obj_id).delete()
            super(DeleteProjectAction, self).delete(request, obj_id)

class RescopeTokenToProject(BaseRescopeTokenToProject):

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
            
        return shortcuts.redirect(reverse_lazy('horizon:idmanager:project_manager:index'))

def get_prj_status(data):
    if data.status == PRJ_GUEST:
        return _("Guest")
    elif data.status == PRJ_PUBLIC:
        return _("Public")
    return _("Private")

class ProjectsTable(TenantsTable):
    status = tables.Column(get_prj_status, verbose_name=_('Status'), status=True)

    class Meta:
        name = "projects"
        verbose_name = _("Projects")
        row_actions = (UpdateMembersLink, UpdateGroupsLink, UpdateProject,
                       UsageLink, ModifyQuotas, ToggleVisibility,
                       DeleteTenantsAction, RescopeTokenToProject)
        table_actions = (TenantFilterAction, CreateProject,
                         DeleteProjectAction)
        pagination_param = "tenant_marker"


