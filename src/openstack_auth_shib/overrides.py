import logging
import horizon

from openstack_dashboard.dashboards.admin.projects.panel import Tenants
from openstack_dashboard.dashboards.admin.users.panel import Users

#
# TODO verify workaround
#
import openstack_dashboard.dashboards.admin.registration_manager.panel
import openstack_dashboard.dashboards.admin.project_manager.panel
import openstack_dashboard.dashboards.admin.user_manager.panel
#import openstack_dashboard.dashboards.project.subscription_manager.panel

LOG = logging.getLogger(__name__)

LOG.debug("Registering panel for the registration manager")
admin_dash = horizon.get_dashboard("admin")
identity_group = admin_dash.get_panel_group('identity')
identity_group.panels.append('registration_manager')

identity_group.panels[1] = 'project_manager'
admin_dash.unregister(Tenants)

identity_group.panels[2] = 'user_manager'
admin_dash.unregister(Users)


