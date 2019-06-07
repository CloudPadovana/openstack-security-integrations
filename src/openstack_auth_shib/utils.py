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
import os
import os.path

from django.conf import settings
from django.db import transaction
from django.utils.translation import ugettext as _

from horizon import forms
from horizon import get_dashboard
from horizon import get_default_dashboard
from horizon import messages
from horizon.base import NotRegistered

from openstack_dashboard.api import keystone as keystone_api
from openstack_dashboard.api import cinder as cinder_api
from openstack_dashboard.api import nova as nova_api
from openstack_dashboard.api import neutron as neutron_api


from .models import Project
from .models import PrjRequest
from .models import PrjRole
from .models import PSTATUS_PENDING
from .models import PSTATUS_RENEW_MEMB

LOG = logging.getLogger(__name__)

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
TENANTADMIN_ROLEID = getattr(settings, 'TENANTADMIN_ROLE_ID', None)

PRJ_REGEX = re.compile(r'[^a-zA-Z0-9-_ ]')
REQID_REGEX = re.compile(r'^([0-9]+):([a-zA-Z0-9-_ ]*)$')

ORG_TAG_FMT = "O=%s"
OU_TAG_FMT = "OU=%s"
TAG_REGEX = re.compile(r'([a-zA-Z0-9-_]+)=([^\s,/]+)$')

def get_admin_roleid(request):
    global TENANTADMIN_ROLEID
    if TENANTADMIN_ROLEID == None:
        for role in keystone_api.keystoneclient(request).roles.list():
            if role.name == TENANTADMIN_ROLE:
                TENANTADMIN_ROLEID = role.id
    return TENANTADMIN_ROLEID


def get_prjman_ids(request, project_id):
    result = list()

    #kclient = keystone_api.keystoneclient(request, admin=True)
    #tntadm_role_id = get_admin_roleid(request)

    #url = '/role_assignments?scope.project.id=%s&role.id=%s'
    #resp, body = kclient.get(url % (project_id, tntadm_role_id))

    #for item in body['role_assignments']:
    #    result.append(item['user']['id'])

    for item in PrjRole.objects.filter(project__projectid = project_id):
        if item.registration.userid:
            result.append(item.registration.userid)

    return result

def get_user_home(user):

    try:

        if user.is_superuser:
            return get_dashboard('admin').get_absolute_url()

        if user.has_perms(('openstack.roles.' + TENANTADMIN_ROLE,)):
        
            q_args = {
                'project__projectname' : user.tenant_name,
                'flowstatus__in' : [ PSTATUS_PENDING, PSTATUS_RENEW_MEMB ]
            }
            if PrjRequest.objects.filter(**q_args).count() > 0:
                idmanager_url = get_dashboard('idmanager').get_absolute_url()
                return idmanager_url + 'subscription_manager/'

    except NotRegistered:
        LOG.error("Cannot retrieve user home", exc_info=True)

    return get_default_dashboard().get_absolute_url()

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

def get_avail_networks(request):

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

    for unit_id, unit_data in unit_table.items():

        result = list()

        used_ipprefs = used_nets.get(unit_data['lan_net_pool'], [])
        max_avail = max(used_ipprefs) if len(used_ipprefs) > 0 else 0

        if max_avail < 255:
            tmpl = list(set(range(1, max_avail + MAX_AVAIL + 1)) - set(used_ipprefs))
            tmpl.sort(lambda x,y: x-y)
            for idx in tmpl:
                result.append("%s.%d.0/24" % (unit_data['lan_net_pool'], idx))

        avail_nets[unit_id] = result

    return avail_nets


def setup_new_project(request, project_id, project_name, data):

    unit_id = data.get('unit', None)

    cloud_table = get_unit_table()
    if not unit_id or not unit_id in cloud_table:
        return

    unit_data = cloud_table[unit_id]
    prj_cname = re.sub(r'\s+', "-", project_name)
    flow_step = 0

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
            messages.error(request, _("Cannot setup project quota"))

    try:

        hyper_list = unit_data.get('hypervisors', [])
        if len(hyper_list):
            agg_prj_cname = "%s-%s" % (unit_data.get('aggregate_prefix', unit_id), prj_cname)
            avail_zone = unit_data.get('availability_zone', 'nova')

            new_aggr = nova_api.aggregate_create(request, agg_prj_cname, avail_zone)
            flow_step += 1

            for h_item in hyper_list:
                nova_api.add_host_to_aggregate(request, new_aggr.id, h_item)
            flow_step += 1

            all_md = { 'filter_tenant_id' : project_id }
            all_md.update(unit_data.get('metadata', {}))

            nova_api.aggregate_set_metadata(request, new_aggr.id, all_md)
            flow_step = 0

    except:
        if flow_step == 0:
            err_msg = _("Cannot create host aggregate")
        elif flow_step == 1:
            err_msg = _("Cannot insert hypervisor in aggregate")
        else:
            err_msg = _("Cannot set metadata for aggregate")
        LOG.error(err_msg, exc_info=True)
        messages.error(request, err_msg)

    try:

        subnet_cidr = data['%s-net' % unit_id]
        prj_lan_name = "%s-lan" % prj_cname

        prj_net = neutron_api.network_create(request, tenant_id=project_id, name=prj_lan_name)
        flow_step += 1

        net_args = {
            'cidr' : subnet_cidr,
            'ip_version' : 4,
            'dns_nameservers' : unit_data.get('nameservers', []),
            'enable_dhcp' : True,
            'tenant_id' : project_id,
            'name' : "sub-%s-lan" % prj_cname
        }
        prj_sub = neutron_api.subnet_create(request, prj_net['id'], **net_args)
        flow_step += 1

        if 'lan_router' in unit_data:
            neutron_api.router_add_interface(request, unit_data['lan_router'], 
                                            subnet_id=prj_sub['id'])
        flow_step = 0

    except:
        if flow_step == 0:
            err_msg = _("Cannot create network")
        elif flow_step == 1:
            err_msg = _("Cannot create sub-network")
        else:
            err_msg = _("Cannot add interface to router")
        LOG.error(err_msg, exc_info=True)
        messages.error(request, err_msg)

    try:
        subnet_cidr = data['%s-net' % unit_id]
        def_sec_group = None
        for sg_item in neutron_api.security_group_list(request, tenant_id=project_id):
            if sg_item['name'].lower() == 'default':
                def_sec_group = sg_item['id']
                LOG.info("Found default security group %s" % def_sec_group)
                break
        flow_step += 1

        sg_client = neutron_api.SecurityGroupManager(request).client

        if not def_sec_group:
            sg_params = {
                'name': 'default',
                'description': 'Default Security Group for ' + project_name,
                'tenant_id': project_id
            }
            secgroup = sg_client.create_security_group({ 'security_group' : sg_params })
            def_sec_group = SecurityGroup(secgroup.get('security_group'))
        flow_step += 1

        #
        # Workaround: the tenant_id cannot be specified through high level API
        #
        port22_params = {
            'security_group_id': def_sec_group,
            'direction': 'ingress',
            'ethertype': 'IPv4',
            'protocol': 'tcp',
            'port_range_min': 22,
            'port_range_max': 22,
            'remote_ip_prefix': "0.0.0.0/0",
            'tenant_id' : project_id
        }

        icmp_params = {
            'security_group_id': def_sec_group,
            'direction': 'ingress',
            'ethertype': 'IPv4',
            'protocol': 'icmp',
            'remote_ip_prefix': "0.0.0.0/0",
            'tenant_id' : project_id
        }

        sg_client.create_security_group_rule({'security_group_rule': port22_params})

        sg_client.create_security_group_rule({'security_group_rule': icmp_params})

    except:
        if flow_step == 0:
            err_msg = _("Cannot retrieve default security group")
        elif flow_step == 1:
            err_msg = _("Cannot create default security group")
        else:
            err_msg = _("Cannot insert basic rules")
        LOG.error(err_msg, exc_info=True)
        messages.error(request, err_msg)

    try:

        new_tags = list()
        new_tags.append(ORG_TAG_FMT % unit_data.get('organization', 'other'))

        for ou_id in data.get('%s-ou' % unit_id, []):
            if ou_id.strip():
                new_tags.append(OU_TAG_FMT % ou_id.strip())

        kclient = keystone_api.keystoneclient(request)
        kclient.projects.update_tags(project_id, new_tags)

    except:
        LOG.error("Cannot add organization tags", exc_info=True)
        messages.error(request, _("Cannot add organization tags"))

def add_unit_combos(newprjform):

    unit_table = get_unit_table()
    org_table = settings.HORIZON_CONFIG.get('organization', {})

    if len(unit_table) > 0:

        avail_nets = get_avail_networks(newprjform.request)

        choices_u = list()
        for k, v in unit_table.items():
            if len(avail_nets[k]) > 0:
                choices_u.append((k,v['name']))

        
        newprjform.fields['unit'] = forms.ChoiceField(
            label=_('Available units'),
            required=True,
            choices=choices_u,
            widget=forms.Select(attrs={
                'class': 'switchable',
                'data-slug': 'unitselector'
            })
        )

        for unit_id, unit_data in unit_table.items():

            if len(avail_nets[unit_id]) == 0:
                continue

            newprjform.fields["%s-net" % unit_id] = forms.ChoiceField(
                label=_('Available networks'),
                required=False,
                choices=[ (k,k) for k in avail_nets[unit_id] ],
                widget=forms.Select(attrs={
                    'class': 'switched',
                    'data-switch-on': 'unitselector',
                    'data-unitselector-%s' % unit_id : _('Available networks')
                })
            )

            ou_list = org_table.get(unit_data.get('organization', ""), None)
            if not ou_list:
                continue

            newprjform.fields["%s-ou" % unit_id] = forms.MultipleChoiceField(
                label=_('Unit or department'),
                required=False,
                choices=[ x[:2] for x in ou_list ],
                widget=forms.SelectMultiple(attrs={
                    'class': 'switched',
                    'data-switch-on': 'unitselector',
                    'data-unitselector-%s' % unit_id : _('Unit or department')
                })
            )


#
# Workaround for unit_table reloading at runtime
#
def get_unit_table():

    unit_filename = os.environ.get("CLOUDVENETO_UNITTABLE", 
                                   "/etc/openstack-dashboard/unit_table.py")
    try:

        if os.path.exists(unit_filename):
            with open(unit_filename) as f:
                exec(f.read())
            return UNIT_TABLE

    except Exception:
        LOG.error("Cannot exec unit table script", exc_info=True)

    return getattr(settings, 'UNIT_TABLE', {})


