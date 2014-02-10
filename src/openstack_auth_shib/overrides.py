import logging
import horizon

LOG = logging.getLogger(__name__)

LOG.debug("Registering panel for the registration manager")
admin_dash = horizon.get_dashboard("admin")
identity_group = admin_dash.get_panel_group('identity')
identity_group.panels.append('registration_manager')
identity_group.panels.append('project_manager')

#
# TODO verify workaround
#
import openstack_dashboard.dashboards.admin.registration_manager.panel
import openstack_dashboard.dashboards.admin.project_manager.panel


