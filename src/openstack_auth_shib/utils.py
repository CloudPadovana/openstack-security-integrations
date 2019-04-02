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
import re

from django.conf import settings
from django.db import transaction
import horizon
from openstack_dashboard.api import keystone as keystone_api

from .models import Project
from .models import PrjRequest
from .models import PSTATUS_PENDING
from .models import PSTATUS_RENEW_MEMB

LOG = logging.getLogger(__name__)

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
TENANTADMIN_ROLEID = getattr(settings, 'TENANTADMIN_ROLE_ID', None)

PRJ_REGEX = re.compile(r'[^a-zA-Z0-9-_ ]')

def get_admin_roleid(request):
    global TENANTADMIN_ROLEID
    if TENANTADMIN_ROLEID == None:
        for role in keystone_api.keystoneclient(request).roles.list():
            if role.name == TENANTADMIN_ROLE:
                TENANTADMIN_ROLEID = role.id
    return TENANTADMIN_ROLEID


def get_prjman_ids(request, project_id):
    result = list()

    kclient = keystone_api.keystoneclient(request, admin=True)
    tntadm_role_id = get_admin_roleid(request)

    url = '/role_assignments?scope.project.id=%s&role.id=%s'
    resp, body = kclient.get(url % (project_id, tntadm_role_id))

    for item in body['role_assignments']:
        result.append(item['user']['id'])

    return result

def get_project_managers(request, project_id):
    result = list()

    for item in get_prjman_ids(request, project_id):
        tntadmin = keystone_api.user_get(request, item)
        result.append(tntadmin)

    return result

def get_user_home(user):

    try:

        if user.is_superuser:
            return horizon.get_dashboard('admin').get_absolute_url()

        if user.has_perms(('openstack.roles.' + TENANTADMIN_ROLE,)):
        
            q_args = {
                'project__projectname' : user.tenant_name,
                'flowstatus__in' : [ PSTATUS_PENDING, PSTATUS_RENEW_MEMB ]
            }
            if PrjRequest.objects.filter(**q_args).count() > 0:
                idmanager_url = horizon.get_dashboard('idmanager').get_absolute_url()
                return idmanager_url + 'subscription_manager/'

    except horizon.base.NotRegistered:
        LOG.error("Cannot retrieve user home", exc_info=True)

    return horizon.get_default_dashboard().get_absolute_url()

def get_ostack_attributes(request):
    region = getattr(settings, 'OPENSTACK_KEYSTONE_URL').replace('v2.0','v3')
    domain = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN', 'Default')
    return (domain, region)

