from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.admin import dashboard

class ProjectManager(horizon.Panel):
    name = _("Projects (new)")
    slug = 'project_manager'

dashboard.Admin.register(ProjectManager)
