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

#from openstack_dashboard.dashboards.identity.projects.panel import Tenants
#from openstack_dashboard.dashboards.identity.users.panel import Users
#from openstack_dashboard.dashboards.settings.password.panel import PasswordPanel

#
# Panels must be loaded in advance
#
import openstack_dashboard.dashboards.identity.registration_manager.panel
#import openstack_dashboard.dashboards.identity.project_manager.panel
#import openstack_dashboard.dashboards.identity.user_manager.panel
import openstack_dashboard.dashboards.identity.subscription_manager.panel
import openstack_dashboard.dashboards.identity.member_manager.panel
import openstack_dashboard.dashboards.identity.project_requests.panel
#import openstack_dashboard.dashboards.identity.idp_requests.panel
#import openstack_dashboard.dashboards.settings.password_manager.panel

LOG = logging.getLogger(__name__)

identity_dash = horizon.get_dashboard("identity")
identity_dash.panels = ('domains', 'projects', 'users', 'groups', 'roles', 'registration_manager',)

#identity_dash.unregister(Tenants)
#identity_dash.unregister(Users)

#settings_dash = horizon.get_dashboard("settings")
#settings_dash.panels = ('user', 'password_manager', )

#settings_dash.unregister(PasswordPanel)



