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
from django.urls import reverse
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

    def allowed(self, request, datum):
        return datum.managed and super(UpdateMembersLink, self).allowed(request, datum)

    def get_link_url(self, project):
        step = 'update_members'
        base_url = reverse(self.url, args=[project.id])
        param = urlencode({"step": step})
        return "?".join([base_url, param])

class UpdateGroupsLink(baseTables.UpdateGroupsLink):
    url = "horizon:idmanager:project_manager:update"

    def allowed(self, request, datum):
        return datum.managed and super(UpdateGroupsLink, self).allowed(request, datum)

class UpdateProject(baseTables.UpdateProject):
    url = "horizon:idmanager:project_manager:update"

    def allowed(self, request, datum):
        return datum.managed and super(UpdateProject, self).allowed(request, datum)

class UsageLink(baseTables.UsageLink):
    url = "horizon:idmanager:project_manager:usage"

    def allowed(self, request, datum):
        return datum.managed and super(UsageLink, self).allowed(request, datum)

class ModifyQuotas(baseTables.ModifyQuotas):
    url = "horizon:idmanager:project_manager:update_quotas"

    def allowed(self, request, datum):
        return datum.managed and super(ModifyQuotas, self).allowed(request, datum)

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

    def allowed(self, request, datum):
        return datum.managed and super(RescopeTokenToProject, self).allowed(request, datum)

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
        return datum.managed and (datum.status == PRJ_PRIVATE or datum.status == PRJ_PUBLIC)

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

class CourseOnLink(tables.LinkAction):
    name = "courseon"
    verbose_name = _("Enable course")
    url = "horizon:idmanager:project_manager:course"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.handle_course and datum.status != PRJ_COURSE

class EditCourseLink(tables.LinkAction):
    name = "editcourse"
    verbose_name = _("Edit course")
    url = "horizon:idmanager:project_manager:course"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return datum.handle_course and datum.status == PRJ_COURSE

class ViewCourseLink(tables.LinkAction):
    name = "viewcourse"
    verbose_name = _("Get course URL")
    url = "horizon:idmanager:project_manager:course_detail"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return datum.handle_course and datum.status == PRJ_COURSE

class CourseOffLink(tables.Action):
    name = "courseoff"
    verbose_name = _("Disable course")

    def allowed(self, request, datum):
        return datum.handle_course and datum.status == PRJ_COURSE

    def single(self, data_table, request, object_id):
    
        with transaction.atomic():
        
            prj_list = Project.objects.filter(projectid=object_id)
            if len(prj_list):
                prj_list[0].status = PRJ_PUBLIC
                prj_list[0].save()
            
        return shortcuts.redirect(reverse('horizon:idmanager:project_manager:index'))

class EditTagsLink(tables.LinkAction):
    name = "edittags"
    verbose_name = _("Edit tags")
    url = "horizon:idmanager:project_manager:edittags"
    classes = ("ajax-modal", "btn-edit")

    def allowed(self, request, datum):
        return datum.managed and request.user.is_superuser

def get_prj_status(data):
    if not data.managed:
        return _("Un-managed")
    if data.status == PRJ_PUBLIC:
        return _("Public")
    if data.status == PRJ_COURSE:
        return _("Course")
    return _("Private")

def get_prj_tags(data):
    if not data.tags:
        return '-'
    tmps = data.tags.pop()
    for ptag in data.tags:
        tmps = tmps + "," + ptag
    return tmps
    
class ProjectsTable(baseTables.TenantsTable):
    tags = tables.Column(get_prj_tags, verbose_name=_('Tags'))
    status = tables.Column(get_prj_status, verbose_name=_('Status'))

    def __init__(self, request, data=None, needs_form_wrapper=None, **kwargs):
        super(ProjectsTable, self).__init__(request, data=data,
                                            needs_form_wrapper=needs_form_wrapper, **kwargs)
        # patch for ajax update disabled
        self.columns['name'].update_action = None
        if 'description' in self.columns:
            self.columns['description'].update_action = None
        self.columns['enabled'].update_action = None
        # end of patch

        # patch for columns removal
        del(self.columns['domain_name'])
        if not request.user.is_superuser:
            del(self.columns['tags'])
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
                       CourseOnLink,
                       EditCourseLink,
                       ViewCourseLink,
                       CourseOffLink,
                       EditTagsLink,
                       DeleteProjectAction,
                       RescopeTokenToProject)
        table_actions = (baseTables.TenantFilterAction, 
                         CreateProject,
                         ReqProjectLink,
                         DeleteProjectAction)
        pagination_param = "tenant_marker"


