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
from django.utils.translation import ugettext as _
import horizon

from openstack_dashboard.api import keystone as keystone_api
from openstack_dashboard.api import cinder as cinder_api
from openstack_dashboard.api import nova as nova_api
from openstack_dashboard.api import neutron as neutron_api


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

def check_projectname(prjname, error_class):
    tmps = prjname.strip()
    if not tmps:
        raise error_class(_('Project name is required.'))
    tmpm = PRJ_REGEX.search(tmps)
    if tmpm:
        raise error_class(_('Bad character "%s" for project name.') % tmpm.group(0))
    return tmps


#
# Project post creation
#

#
# {
#   <unit_id> : {
#     "name" : <human readable unit name>,
#     "organization" : <organization tag>,
#     "quota_total" :  <total>,
#     "quota_per_volume" : <per-volume>,
#     "quota_<type>" : <quota_type>,
#
#     "availability_zone" : <availability zone, default: nova>
#     "aggregate_prefix" : <project_prefix>,
#     "hypervisors" : <list_of_hypervisors>,
#     "metadata" : <hash of metadata>,
#
#     "lan_net_pool" : <2-octets network ip prefix>,
#     "lan_router" : <router name>,
#     "nameservers" : <list of dns ip>,
# }
#

CIDR_PATTERN = re.compile("(\d+\.\d+)\.(\d+).0/\d+")
MAX_AVAIL = getattr(settings, 'MAX_PROPOSED_NETWORKS', 10)

def get_avail_subnets(request):

    unit_table = getattr(settings, 'UNIT_TABLE', {})

    used_nets = dict()
    for subdict in neutron_api.subnet_list(request):
        cidr_match = CIDR_PATTERN.search(subdict['cidr'])
        if not cidr_match:
            continue
        if not cidr_match.group(1) in used_nets:
            used_nets[cidr_match.group(1)] = list()
        used_nets[cidr_match.group(1)].append(int(cidr_match.group(2)))

    avail_nets = dict()
    for subprx, subnums in used_nets.items():

        tmpa = [ k for k, v in unit_table.items() if v['lan_net_pool'] == subprx ]
        if len(tmpa) == 0:
            continue
        unit_id = tmpa[0]

        avail_nets[unit_id] = list()

        max_avail = max(subnums)
        if max_avail == 255:
            continue

        tmpl = list(set(range(max_avail + MAX_AVAIL + 1)) - set(subnums))
        tmpl.sort(lambda x,y: y-x)

        for idx in tmpl:
            avail_nets[unit_id].append("%s.%d.0/24" % (subprx, idx))

    return avail_nets


def setup_new_project(request, project_id, project_name, data):

    unit_id = data.get('unit', None)

    cloud_table = getattr(settings, 'UNIT_TABLE', {})
    if not unit_id or not unit_id in cloud_table:
        return

    unit_data = cloud_table[unit_id]
    prj_cname = re.sub(r'\s+', "-", project_name)

    try:

        cinder_params = dict()
        for pkey, pvalue in unit_data.items():
            if pkey == 'quota_total':
                cinder_params['gigabytes'] = pvalue
            elif pkey == 'quota_per_volume':
                cinder_params['per_volume_gigabytes'] = pvalue
            elif pkey.startswith('quota_'):
                cinder_params['gigabytes_' + pkey[6:]] = pvalue

        if len(cinder_params):
            cinder_api.tenant_quota_update(request, project_id, **cinder_params)

    except:
            LOG.error("Cannot setup project quota", exc_info=True)
            horizon.messages.error(request, _("Cannot setup project quota"))

    try:

        hyper_list = unit_data.get('hypervisors', [])
        if len(hyper_list):
            agg_prj_cname = "%s-%s" % (unit_data.get('aggregate_prefix', unit_id), prj_cname)
            avail_zone = unit_data.get('availability_zone', 'nova')

            new_aggr = nova_api.aggregate_create(request, agg_prj_cname, avail_zone)

            for h_item in hyper_list:
                nova_api.add_host_to_aggregate(request, new_aggr.id, h_item)

            all_md = { 'filter_tenant_id' : project_id }
            all_md.update(unit_data.get('metadata', {}))

            nova_api.aggregate_set_metadata(request, new_aggr.id, all_md)

    except:
            LOG.error("Cannot setup host aggregate", exc_info=True)
            horizon.messages.error(request, _("Cannot setup host aggregate"))

    try:

        subnet_cidr = data['%s-net' % unit_id]
        prj_lan_name = "%s-lan" % prj_cname

        prj_net = neutron_api.network_create(request, tenant_id=project_id, name=prj_lan_name)
        net_args = {
            'cidr' : subnet_cidr,
            'ip_version' : 4,
            'dns_nameservers' : unit_data.get('nameservers', []),
            'enable_dhcp' : True,
            'tenant_id' : project_id,
            'name' : "sub-%s-lan" % prj_cname
        }
        prj_sub = neutron_api.subnet_create(request, prj_net['id'], **net_args)
        if 'lan_router' in unit_data:
            neutron_api.router_add_interface(request, unit_data['lan_router'], 
                                            subnet_id=prj_sub['id'])

    except:
            LOG.error("Cannot setup networks", exc_info=True)
            horizon.messages.error(request, _("Cannot setup networks"))

    try:
        subnet_cidr = data['%s-net' % unit_id]
        def_sec_group = None
        for sg_item in neutron_api.security_group_list(request, tenant_id=project_id):
            if sg_item['name'].lower() == 'default':
                def_sec_group = sg_item['id']
                LOG.info("Found default security group %s" % def_sec_group)
                break

#        if not def_sec_group:
#            sg_client = neutron_api.SecurityGroupManager(request).client
#
#            sg_args = { 'name': 'default',
#                        'description': 'Default Security Group for ' + project_name,
#                        'tenant_id': project_id }
#            secgroup = sg_client.create_security_group({ 'security_group' : sg_args })
#            def_sec_group = SecurityGroup(secgroup.get('security_group'))

        neutron_api.security_group_rule_create(request, def_sec_group, 'ingress',
                                                'IPv4','tcp', 22, 22,
                                               subnet_cidr, None)
        neutron_api.security_group_rule_create(request, def_sec_group, 'ingress',
                                                'IPv4','icmp', None, None,
                                               subnet_cidr, None)
    except:
            LOG.error("Cannot update default security group", exc_info=True)
            horizon.messages.error(request, _("Cannot update default security group"))

    try:

        kclient = keystone_api.keystoneclient(request)
        kclient.projects.add_tag(project_id, unit_data.get('organization', 'other'))

    except:
            LOG.error("Cannot add organization tag", exc_info=True)
            horizon.messages.error(request, _("Cannot add organization tag"))

