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

from django.conf import settings
from django.db import transaction
from openstack_dashboard.api import keystone as keystone_api

from .models import Project, PRJ_GUEST

LOG = logging.getLogger(__name__)

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
TENANTADMIN_ROLEID = None

DEFAULT_ROLE = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', '')
DEFAULT_ROLEID = None

def get_admin_roleid(request):
    global TENANTADMIN_ROLEID
    if TENANTADMIN_ROLEID == None:
        for role in keystone_api.role_list(request):
            if role.name == TENANTADMIN_ROLE:
                TENANTADMIN_ROLEID = role.id
        if not TENANTADMIN_ROLEID:
            TENANTADMIN_ROLEID = keystone_api.role_create(request, TENANTADMIN_ROLE)
    return TENANTADMIN_ROLEID

def get_default_roleid(request):
    global DEFAULT_ROLEID
    if DEFAULT_ROLEID == None:
        for role in keystone_api.role_list(request):
            if role.name == DEFAULT_ROLE:
                DEFAULT_ROLEID = role.id
    return DEFAULT_ROLEID


def get_project_managers(request, project_id):
    result = list()

    kclient = keystone_api.keystoneclient(request, admin=True)
    tntadm_role_id = get_admin_roleid(request)
    
    url = '/role_assignments?scope.project.id=%s&role.id=%s'
    resp, body = kclient.get(url % (project_id, tntadm_role_id))
    
    for item in body['role_assignments']:
        tntadmin = keystone_api.user_get(request, item['user']['id'])
        LOG.debug('Found tenant admin %s' % tntadmin.name)
        result.append(tntadmin)
        
    return result

GUEST_IMPORTED = False
def import_guest_project():
    global GUEST_IMPORTED

    if GUEST_IMPORTED:
        return

    guest_data = getattr(settings, 'GUEST_PROJECT', None)
    if not guest_data:
        return
    
    try:
        prjname = guest_data['name'].strip()
        prjid = guest_data['id'].strip()
        prjdescr = guest_data.get('description', 'Guest project')
        
        with transaction.commit_on_success():
            try:
                guestprj = Project.objects.get(projectname=prjname)
            except Project.DoesNotExist:
                p_query = {
                    'projectname' : prjname,
                    'projectid' : prjid,
                    'description' : prjdescr,
                    'status' : PRJ_GUEST
                }
                imprj = Project(**p_query)
                imprj.save()
                LOG.info("Imported guest project %s" % prjname)
                
        GUEST_IMPORTED = True
    except:
        LOG.error("Failed guest auto-import", exc_info=True)



