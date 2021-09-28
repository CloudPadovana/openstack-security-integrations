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

from openstack_dashboard.dashboards.project.api_access import views as baseViews
from .tables import EndpointsTable

LOG = logging.getLogger(__name__)

def download_os_token_file(request):

    template = 'project/api_access_manager/openrc.sh.template'

    context = baseViews._get_openrc_credentials(request)
    context['user_domain_name'] = request.user.user_domain_name
    try:
        project_domain_id = request.user.token.project['domain_id']
    except KeyError:
        project_domain_id = ''
    context['project_domain_id'] = project_domain_id
    context['os_identity_api_version'] = 3
    context['os_auth_version'] = 3

    context['os_auth_token'] = request.session.get('unscoped_token')

    return baseViews._download_rc_file_for_template(request, context, template)

class IndexView(baseViews.IndexView):
    table_class = EndpointsTable
