
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

class ProjectsTable(TenantsTable):
    visible = tables.Column('visible', verbose_name=_('Visible'), status=True)

    class Meta:
        name = "projects"
        verbose_name = _("Projects (new)")
        row_actions = (ViewMembersLink, ViewGroupsLink, UpdateProject,
                       UsageLink, ModifyQuotas, DeleteTenantsAction)
        table_actions = (TenantFilterAction, CreateProject,
                         DeleteTenantsAction)
        pagination_param = "tenant_marker"

