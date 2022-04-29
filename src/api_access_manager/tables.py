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

from horizon import tables
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from openstack_dashboard.dashboards.project.api_access import tables as baseTables

from openstack_auth_shib.idpmanager import Federated_Account

class DownloadEC2(baseTables.DownloadEC2):
    url = "horizon:project:api_access_manager:ec2"

class DownloadCloudsYaml(baseTables.DownloadCloudsYaml):
    url = "horizon:project:api_access_manager:clouds.yaml"

class DownloadOpenRC(baseTables.DownloadOpenRC):
    url = "horizon:project:api_access_manager:openrc"

    def allowed(self, request, datum=None):
        #return settings.SHOW_OPENRC_FILE and not Federated_Account(request)
        return settings.SHOW_OPENRC_FILE

class DownloadOSToken(tables.LinkAction):
    name = "download_os_token"
    verbose_name = _("OpenStack Token File")
    verbose_name_plural = _("OpenStack Token File")
    icon = "download"
    url = "horizon:project:api_access_manager:ostoken"

class ViewCredentials(baseTables.ViewCredentials):
    url = "horizon:project:api_access_manager:view_credentials"

class RecreateCredentials(baseTables.RecreateCredentials):
    url = "horizon:project:api_access_manager:recreate_credentials"

class EndpointsTable(tables.DataTable):
    api_name = tables.Column('type',
                             verbose_name=_("Service"),
                             filters=(baseTables.pretty_service_names,))
    api_endpoint = tables.Column('public_url',
                                 verbose_name=_("Service Endpoint"))

    class Meta(object):
        name = "endpoints"
        verbose_name = _("API Endpoints")
        multi_select = False
        table_actions = (ViewCredentials,
                         RecreateCredentials)
        table_actions_menu = (DownloadCloudsYaml,
                              DownloadOpenRC,
                              DownloadOSToken,
                              DownloadEC2)
        table_actions_menu_label = _('Download OpenStack RC File')

