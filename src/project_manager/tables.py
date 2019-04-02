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

from openstack_dashboard import policy
from openstack_dashboard.dashboards.identity.projects import tables as baseTables

from openstack_auth_shib.models import Project, PrjRequest
from openstack_auth_shib.models import PRJ_PRIVATE
from openstack_auth_shib.models import PRJ_PUBLIC
from openstack_auth_shib.models import PRJ_COURSE

LOG = logging.getLogger(__name__)

class UpdateMembersLink(baseTables.UpdateMembersLink):
    url = "horizon:idmanager:project_manager:update"

    def get_link_url(self, project):
        step = 'update_members'
        base_url = reverse(self.url, args=[project.id])
        param = urlencode({"step": step})
        return "?".join([base_url, param])

class UpdateGroupsLink(baseTables.UpdateGroupsLink):
    url = "horizon:idmanager:project_manager:update"
    
class UpdateProject(baseTables.UpdateProject):
    url = "horizon:idmanager:project_manager:update"

class UsageLink(baseTables.UsageLink):
    url = "horizon:idmanager:project_manager:usage"
    
class ModifyQuotas(baseTables.ModifyQuotas):
    url = "horizon:idmanager:project_manager:update_quotas"

class CreateProject(baseTables.CreateProject):
    url = "horizon:idmanager:project_manager:create"

class DeleteProjectAction(baseTables.DeleteTenantsAction):

    def delete(self, request, obj_id):
    
        with transaction.atomic():

            for prjreq in PrjRequest.objects.filter(project__projectid=obj_id):
                if not prjreq.registration.userid:
                    messages.error(request,
                        _("Cannot delete project: there are pending registrations"))
                    raise Exception("Pending registrations")

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

    def allowed(self, request, datum):
        return datum.status == PRJ_PRIVATE or datum.status == PRJ_PUBLIC

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
            
        return shortcuts.redirect(reverse('horizon:idmanager:project_manager:index'))

class ReqProjectLink(tables.LinkAction):
    name = "reqproject"
    verbose_name = _("Subscribe to project")
    url = "horizon:idmanager:project_requests:index"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return not request.user.is_superuser

def get_prj_status(data):
    elif data.status == PRJ_PUBLIC:
        return _("Public")
    elif data.status == PRJ_COURSE:
        return _("Course")
    return _("Private")

class ProjectsTable(baseTables.TenantsTable):
    status = tables.Column(get_prj_status, verbose_name=_('Status'), status=True)

    # patch for ajax update disabled
    def __init__(self, request, data=None, needs_form_wrapper=None, **kwargs):
        super(ProjectsTable, self).__init__(request, data=data,
                                            needs_form_wrapper=needs_form_wrapper, **kwargs)
        self.columns['name'].update_action = None
        if 'description' in self.columns:
            self.columns['description'].update_action = None
        self.columns['enabled'].update_action = None
    # end of patch

    def get_project_detail_link(self, project):
        if policy.check((("identity", "identity:get_project"),),
                        self.request, target={"project": project}):
            return reverse("horizon:idmanager:project_manager:detail",
                           args=(project.id,))
        return None

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


