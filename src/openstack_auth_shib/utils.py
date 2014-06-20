
import logging

from django.conf import settings
from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
TENANTADMIN_ROLEID = None

def get_admin_roleid(request):
    global TENANTADMIN_ROLEID
    if TENANTADMIN_ROLEID == None:
        for role in keystone_api.role_list(request):
            if role.name == TENANTADMIN_ROLE:
                TENANTADMIN_ROLEID = role.id
    return TENANTADMIN_ROLEID


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

