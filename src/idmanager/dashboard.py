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

from django.utils.translation import gettext_lazy as _

import horizon

class IdentityManager(horizon.Dashboard):
    name = _("Identity")
    slug = "idmanager"
    default_panel = 'project_manager'

horizon.register(IdentityManager)

# workaround: just hide the identity dashboard
identity_dashboard = horizon.get_dashboard('identity')
identity_dashboard.nav = False


