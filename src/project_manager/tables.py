import logging

from django import shortcuts
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

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
        #
        # TODO bad query, extract username from data_table (ProjectsTable)
        #
        prj_list = Project.objects.filter(projectid=object_id)
        if len(prj_list):
            prj_list[0].visible = not prj_list[0].visible
            prj_list[0].save()
        return shortcuts.redirect(reverse_lazy('horizon:admin:project_manager:index'))

class ProjectsTable(TenantsTable):
    visible = tables.Column('visible', verbose_name=_('Visible'), status=True)

    class Meta:
        name = "projects"
        verbose_name = _("Projects (new)")
        row_actions = (ViewMembersLink, ViewGroupsLink, UpdateProject,
                       UsageLink, ModifyQuotas, ToggleVisibility,
                       DeleteTenantsAction)
        table_actions = (TenantFilterAction, CreateProject,
                         DeleteTenantsAction)
        pagination_param = "tenant_marker"

