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
import horizon

from openstack_dashboard.dashboards.admin.projects.panel import Tenants
from openstack_dashboard.dashboards.admin.users.panel import Users

#
# Panels must be loaded in advance
#
import openstack_dashboard.dashboards.admin.registration_manager.panel
import openstack_dashboard.dashboards.admin.project_manager.panel
import openstack_dashboard.dashboards.admin.user_manager.panel
import openstack_dashboard.dashboards.project.subscription_manager.panel
import openstack_dashboard.dashboards.project.project_requests.panel
import openstack_dashboard.dashboards.settings.password_manager.panel

LOG = logging.getLogger(__name__)

LOG.debug("Registering panel for the registration manager")
admin_dash = horizon.get_dashboard("admin")
identity_group = admin_dash.get_panel_group('identity')
identity_group.panels.append('registration_manager')

identity_group.panels[1] = 'project_manager'
admin_dash.unregister(Tenants)

identity_group.panels[2] = 'user_manager'
admin_dash.unregister(Users)

LOG.debug("Registering panel for the password manager")
settings_dash = horizon.get_dashboard("settings")
defset_group = settings_dash.get_panel_group('default')
defset_group.panels.append('password_manager')




