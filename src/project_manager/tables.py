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
from openstack_dashboard.dashboards.admin.projects.tables import CreateProject
from openstack_dashboard.dashboards.admin.projects.tables import DeleteTenantsAction

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
                    raise Exception(_("Cannot toggle guest project"))
            
        return shortcuts.redirect(reverse_lazy('horizon:admin:project_manager:index'))

class SetGuestProject(tables.Action):
    name = "set_guest_prj"
    verbose_name = _("Set as guest")
    
    def single(self, data_table, request, object_id):

        with transaction.commit_on_success():
            
            prj_list = Project.objects.filter(status=PRJ_GUEST)
            if len(prj_list):
                prj_list[0].status = status=PRJ_PUBLIC
                prj_list[0].save()
            
            prj_list = Project.objects.filter(projectid=object_id)
            if len(prj_list):
                prj_list[0].status = PRJ_GUEST
                prj_list[0].save()

        return shortcuts.redirect(reverse_lazy('horizon:admin:project_manager:index'))

class ProjectsTable(TenantsTable):
    status = tables.Column('status', verbose_name=_('Visible'), status=True)

    class Meta:
        name = "projects"
        verbose_name = _("Projects (new)")
        row_actions = (ViewMembersLink, ViewGroupsLink, UpdateProject,
                       UsageLink, ModifyQuotas, ToggleVisibility,
                       SetGuestProject, DeleteTenantsAction)
        table_actions = (TenantFilterAction, CreateProject,
                         DeleteTenantsAction)
        pagination_param = "tenant_marker"

#
# TODO try to change the object_id form project_id to project_name
#      query on primary key (projectname)
#
