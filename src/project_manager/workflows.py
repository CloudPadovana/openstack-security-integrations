import logging

from openstack_dashboard.dashboards.admin.projects.workflows import UpdateProject as BaseUpdateProject

LOG = logging.getLogger(__name__)

class UpdateProject(BaseUpdateProject):
    success_url = "horizon:admin:project_manager:index"

