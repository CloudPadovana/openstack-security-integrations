from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.project import dashboard

class ProjectRequests(horizon.Panel):
    name = _("Request for projects")
    slug = 'project_requests'

dashboard.Project.register(ProjectRequests)

