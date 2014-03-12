import logging

from django import shortcuts
from django.db import transaction
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext as _

from horizon import tables

from openstack_dashboard.dashboards.admin.projects.tables import TenantsTable

from openstack_dashboard.dashboards.admin.projects.tables import ViewMembersLink as BaseViewMembersLink
from openstack_dashboard.dashboards.admin.projects.tables import ViewGroupsLink as BaseViewGroupsLink
from openstack_dashboard.dashboards.admin.projects.tables import UpdateProject as BaseUpdateProject
from openstack_dashboard.dashboards.admin.projects.tables import UsageLink as BaseUsageLink
from openstack_dashboard.dashboards.admin.projects.tables import ModifyQuotas as BaseModifyQuotas
from openstack_dashboard.dashboards.admin.projects.tables import DeleteTenantsAction

from openstack_dashboard.dashboards.admin.projects.tables import TenantFilterAction
from openstack_dashboard.dashboards.admin.projects.tables import CreateProject as BaseCreateProject

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_PRIVATE, PRJ_PUBLIC, PRJ_GUEST

LOG = logging.getLogger(__name__)

class ViewMembersLink(BaseViewMembersLink):
    url = "horizon:admin:project_manager:update"

class ViewGroupsLink(BaseViewGroupsLink):
    url = "horizon:admin:project_manager:update"
    
class UpdateProject(BaseUpdateProject):
    url = "horizon:admin:project_manager:update"

class UsageLink(BaseUsageLink):
    url = "horizon:admin:project_manager:usage"
    
class ModifyQuotas(BaseModifyQuotas):
    url = "horizon:admin:project_manager:update"

class CreateProject(BaseCreateProject):
    url = "horizon:admin:project_manager:create"

class DeleteProjectAction(DeleteTenantsAction):

    def delete(self, request, obj_id):
    
        with transaction.commit_on_success():
            Project.objects.filter(projectid=obj_id).delete()
            super(DeleteProjectAction, self).delete(request, obj_id)

class ToggleVisibility(tables.Action):
    name = "toggle_visible"
    verbose_name = _("Toggle Visibility")
    
    def single(self, data_table, request, object_id):
    
        with transaction.commit_on_success():
        
            prj_list = Project.objects.filter(projectid=object_id)
            if len(prj_list):
                prj_status = prj_list[0].status
                if prj_status is PRJ_PRIVATE:
                    prj_list[0].status = PRJ_PUBLIC
                    prj_list[0].save()
                elif prj_status is PRJ_PUBLIC:
                    prj_list[0].status = PRJ_PRIVATE
                    prj_list[0].save()
                elif prj_status is PRJ_GUEST:
                    tempDict = {
                        'error_header' : _("Authentication error"),
                        'error_text' : _("Cannot toggle guest project"),
                        'redirect_url' : reverse_lazy('horizon:admin:project_manager:index'),
                        'redirect_label' : _("Projects")
                    }
                    return shortcuts.render(request, 'aai_error.html', tempDict)
            
        return shortcuts.redirect(reverse_lazy('horizon:admin:project_manager:index'))

class SetGuestProject(tables.Action):
    name = "set_guest_prj"
    verbose_name = _("Set as guest")
    
    def single(self, data_table, request, object_id):

        with transaction.commit_on_success():
            
            prj_list = Project.objects.filter(status=PRJ_GUEST)
            if len(prj_list):
                prj_list[0].status = PRJ_PUBLIC
                prj_list[0].save()
            
            prj_list = Project.objects.filter(projectid=object_id)
            if len(prj_list):
                prj_list[0].status = PRJ_GUEST
                prj_list[0].save()

        return shortcuts.redirect(reverse_lazy('horizon:admin:project_manager:index'))

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
        row_actions = (ViewMembersLink, ViewGroupsLink, UpdateProject,
                       UsageLink, ModifyQuotas, ToggleVisibility,
                       SetGuestProject, DeleteProjectAction)
        table_actions = (TenantFilterAction, CreateProject,
                         DeleteProjectAction)
        pagination_param = "tenant_marker"

#
# TODO try to change the object_id form project_id to project_name
#      query on primary key (projectname)
#
