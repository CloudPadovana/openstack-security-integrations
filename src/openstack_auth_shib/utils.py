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

from datetime import datetime
from datetime import timezone
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse_lazy
from django.utils.translation import gettext as _

from horizon import forms
from horizon import get_dashboard
from horizon import get_default_dashboard
from horizon import messages
from horizon.base import NotRegistered

from openstack_dashboard.api import keystone as keystone_api
from openstack_dashboard.api import cinder as cinder_api
from openstack_dashboard.api import nova as nova_api
from openstack_dashboard.api import neutron as neutron_api

from .models import Registration
from .models import Expiration
from .models import Project
from .models import PrjRequest
from .models import PrjRole
from .models import PSTATUS_PENDING
from .models import PSTATUS_RENEW_MEMB
from .models import PSTATUS_RENEW_ATTEMPT

from .models import NEW_MODEL
if NEW_MODEL:
    from .models import PrjAttribute

LOG = logging.getLogger(__name__)

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
TENANTADMIN_ROLEID = getattr(settings, 'TENANTADMIN_ROLE_ID', None)

PRJ_REGEX = re.compile(r'[^a-zA-Z0-9-_ \.]')
REQID_REGEX = re.compile(r'^([0-9]+):([a-zA-Z0-9-_ \.]*)$')

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

        q_args = {
            'registration__userid' : user.id,
            'project__projectname' : user.tenant_name,
            'flowstatus' : PSTATUS_RENEW_ATTEMPT
        }
        if PrjRequest.objects.filter(**q_args).count() > 0:
            return reverse_lazy('horizon:idmanager:project_manager:proposedrenew')

        if user.has_perms(('openstack.roles.' + TENANTADMIN_ROLE,)):
            q_args = {
                'project__projectname' : user.tenant_name,
                'flowstatus__in' : [ PSTATUS_PENDING, PSTATUS_RENEW_MEMB ]
            }
            if PrjRequest.objects.filter(**q_args).count() > 0:
                return reverse_lazy('horizon:idmanager:subscription_manager:index')

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

if NEW_MODEL:
    #
    # Definitions and utilities for courses
    #
    ATT_COURSE_NAME = 1001
    ATT_COURSE_DESC = 1002
    ATT_COURSE_NOTE = 1003
    ATT_COURSE_ORG = 1004
    ATT_COURSE_OU = 1005

    COURSE_ATT_MAP = {
        ATT_COURSE_NAME : 'name',
        ATT_COURSE_DESC : 'description',
        ATT_COURSE_NOTE : 'notes',
        ATT_COURSE_ORG : 'org',
        ATT_COURSE_OU : 'ou'
    }

    def get_course_info(prj_name):
        result = dict()
        c_info = PrjAttribute.objects.filter(project__projectname = prj_name, name__in = COURSE_ATT_LIST)
        for item in c_info:
            result[COURSE_ATT_MAP[item.name]] = item.value
        return result

else:
    #
    # Simple blob structure for course details
    #
    def parse_course_info(blob, default_name=""):
        data = blob.split('|')
        return {
            'description' : data[0] if len(data) else _('Undefined'),
            'name' : data[1] if len(data) > 1 else default_name,
            'notes' : data[2] if len(data) > 2 else "",
            'ou' : data[3] if len(data) > 3 else 'other',
            'org' : data[4] if len(data) > 4 else 'unipd.it'
        }

    def encode_course_info(info_dict, default_name=""):
        return '%s|%s|%s|%s|%s' % (info_dict.get('description', _('Undefined')),
                                   info_dict.get('name', default_name),
                                   info_dict.get('notes', ""),
                                   info_dict.get('ou', 'other'),
                                   info_dict.get('org', 'unipd.it'))

    def check_course_info(info_dict):
        for info_key, info_value in info_dict.items():
            if not '|' in info_value:
                continue
            if info_key == 'name':
                return _('Bad character "|" in the course name.')
            if info_key == 'description':
                return _('Bad character "|" in the course description.')
            if info_key == 'notes':
                return _('Bad character "|" in the course notes.')
            if info_key == 'ou':
                return _('Bad character "|" in the course department.')
            if info_key == 'org':
                return _('Bad character "|" in the course institution.')
        return None

#
# Definitions and utilities for expiration date
#
try:
    YEARS_RANGE = int(getattr(settings, 'YEARS_RANGE', '10'))
except:
    YEARS_RANGE = 10

def get_year_list(n_of_years = YEARS_RANGE):
    curr_year = datetime.now(timezone.utc).year
    return list(range(curr_year, curr_year + n_of_years))

def NOW():
    return datetime.now(timezone.utc)

def FROMNOW(days):
    return datetime.now(timezone.utc) + timedelta(days)

try:
    MAX_RENEW = int(getattr(settings, 'TENANT_MAX_RENEW', '4'))
except:
    MAX_RENEW = 4

ATT_PRJ_EXP = 2001
ATT_PRJ_CPER = 2002

ATT_PRJ_CIDR = 2011
ATT_PRJ_ORG = 2012

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

CIDR_PATTERN = re.compile(r'([0-9]+\.[0-9]+)\.([0-9]+)\.0/[0-9]+')
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
            tmpl.sort()
            for idx in tmpl:
                result.append("%s.%d.0/24" % (unit_data['lan_net_pool'], idx))

        avail_nets[unit_id] = result

    return avail_nets


def setup_new_project(request, project_id, project_name, data):

    try:
        acct_table = getattr(settings, 'ACCOUNTING', None)
        if acct_table:
            uid = acct_table.get('user_id', None)
            roleid = acct_table.get('role_id', None)
            if uid and roleid:
                keystone_api.add_tenant_user_role(request, project_id, uid, roleid)
    except:
        LOG.error("Cannot add user for accounting", exc_info=True)
        messages.error(request, _("Cannot add user for accounting"))

    unit_id = data.get('unit', None)

    cloud_table = get_unit_table()
    if not unit_id or not unit_id in cloud_table:
        return

    unit_data = cloud_table[unit_id]
    prj_cname = re.sub(r'\s+', "-", project_name)
    flow_step = 0
    prj_subnet_cidr = None
    prj_org = None

    ###########################################################################
    # Quota
    ###########################################################################

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

    ###########################################################################
    # Host aggregation
    ###########################################################################

    try:

        hyper_list = unit_data.get('hypervisors', [])
        if len(hyper_list):
            agg_prj_cname = "%s-%s" % (unit_data.get('aggregate_prefix', unit_id), prj_cname)
            avail_zone = unit_data.get('availability_zone', 'nova')

            err_msg = _("Cannot create host aggregate")
            new_aggr = nova_api.aggregate_create(request, agg_prj_cname, avail_zone)

            err_msg = _("Cannot insert hypervisor in aggregate: ")
            for h_item in hyper_list:
                try:
                    nova_api.add_host_to_aggregate(request, new_aggr.id, h_item)
                except:
                    LOG.error(err_msg + new_aggr.name, exc_info=True)

            all_md = { 'filter_tenant_id' : project_id }
            all_md.update(unit_data.get('metadata', {}))

            err_msg = _("Cannot insert hypervisor in aggregate")
            nova_api.aggregate_set_metadata(request, new_aggr.id, all_md)

    except:
        LOG.error(err_msg, exc_info=True)
        messages.error(request, err_msg)

    ###########################################################################
    # Networking
    ###########################################################################

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
        prj_subnet_cidr = prj_sub['cidr']
        flow_step += 1

        if 'lan_router' in unit_data:
            f_ips = [{
                "ip_address" : subnet_cidr.replace('0/24', '1'),
                "subnet_id" : prj_sub['id']
            }]
            r_port = neutron_api.port_create(request, prj_net['id'],
                                             tenant_id=project_id,
                                             project_id=project_id,
                                             fixed_ips=f_ips)

            neutron_api.router_add_interface(request, unit_data['lan_router'], 
                                            port_id=r_port['id'])
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

    ###########################################################################
    # Security groups and rules
    ###########################################################################

    try:
        avail_sgroups = dict()
        for sg_item in neutron_api.security_group_list(request, tenant_id=project_id):
            avail_sgroups[sg_item['name']] = sg_item['id']

        sg_rules_table = getattr(settings, 'SG_RULES_TABLE', {})

        sg_client = neutron_api.SecurityGroupManager(request).client
        for sg_name, sg_rules in sg_rules_table.items():
            if not sg_name in avail_sgroups:
                sg_params = {
                    'name': sg_name,
                    'description': 'Security Group %s for %s' % (sg_name, project_name),
                    'tenant_id': project_id
                }
                raw_sgroup = sg_client.create_security_group({ 'security_group' : sg_params })
                avail_sgroups[sg_name] = raw_sgroup.get('security_group')['id']

            for rule_item in sg_rules:
                r_params = rule_item.copy()
                r_params['security_group_id'] = avail_sgroups[sg_name]
                r_params['tenant_id'] = project_id
                sg_client.create_security_group_rule({ 'security_group_rule' : r_params })
    except:
        LOG.error("Cannot initialized security groups", exc_info=True)
        messages.error(request, _("Cannot initialized security groups"))

    ###########################################################################
    # Project tags
    ###########################################################################

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

    ###########################################################################
    # Project attributes in DB
    ###########################################################################
    if NEW_MODEL:
        # no transactions here
        prj_obj = Project.objects.get(project_name)
        if prj_subnet_cidr:
            PrjAttribute(project = prj_obj, name = ATT_PRJ_CIDR,
                         value = prj_subnet_cidr).save()
        if prj_org:
            PrjAttribute(project = prj_obj, name = ATT_PRJ_ORG,
                         value = prj_org).save()

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

def check_VMs_and_Volumes(request, **kwargs):

    try:        
        kwargs['all_tenants'] = True
        (servers, d1) = nova_api.server_list(request, kwargs, False)
        if len(servers) > 0:
            err_msg = _("Existing instances: ") + '\n'.join([x.name for x in servers])
            LOG.error(err_msg, exc_info=True)
            messages.error(request, err_msg)
            return False

        volumes = cinder_api.volume_list(request, kwargs)
        if len(volumes) > 0:
            err_msg = _("Existing volumes: ") + '\n'.join([x.name for x in volumes])
            LOG.error(err_msg, exc_info=True)
            messages.error(request, err_msg)
            return False

        snapshots = cinder_api.volume_snapshot_list(request, kwargs)
        if len(snapshots) > 0:
            err_msg = _("Existing snapshots: ") + '\n'.join([x.name for x in snapshots])
            LOG.error(err_msg, exc_info=True)
            messages.error(request, err_msg)
            return False
    except:
        LOG.error(_("Failed checks for project removal"), exc_info=True)
        messages.error(request, _("Failed checks for project removal"))
        return False

    return True

def dispose_project(request, project_id):

    if not check_VMs_and_Volumes(request, project_id = project_id):
        return False

    try:
        prj_subnets = set()
        for s_item in neutron_api.subnet_list(request, project_id = project_id):
            prj_subnets.add(s_item.id)

        for r_item in neutron_api.router_list(request):

            for p_item in neutron_api.port_list(request,
                project_id = project_id,
                device_id = r_item.id
            ):
                if p_item.device_owner == "network:router_gateway":
                    continue
                for ip_item in p_item.fixed_ips:
                    if ip_item.get('subnet_id') in prj_subnets:
                        tmpt = (ip_item.get('ip_address'), r_item.name)
                        LOG.info('Removing port %s from %s' % tmpt)
                        neutron_api.router_remove_interface(request, r_item.id, None, p_item.id)

        for s_item in prj_subnets:
            LOG.info('Removing subnet %s' % s_item)
            neutron_api.subnet_delete(request, s_item)

        for n_item in neutron_api.network_list(request, project_id = project_id):
            LOG.info('Removing network %s' % n_item.name)
            neutron_api.network_delete(request, n_item.id)
    except:
        err_msg = _("Cannot remove neutron objects. Manual removal required.")
        LOG.error(err_msg, exc_info=True)
        messages.error(request, err_msg)
        return False

    try:
        for agg_item in nova_api.aggregate_details_list(request):
            if agg_item.metadata.get('filter_tenant_id', '') == project_id:
                for agg_host in agg_item.hosts:
                    LOG.info('Removing host %s from %s' % (agg_host, agg_item.name))
                    nova_api.remove_host_from_aggregate(request, agg_item.id, agg_host)
                LOG.info('Removing aggregate %s' % agg_item.name)
                nova_api.aggregate_delete(request, agg_item.id)
    except:
        err_msg = _("Cannot remove host aggregates. Manual removal required.")
        LOG.error(err_msg, exc_info=True)
        messages.error(request, err_msg)
        return False

    return True

def unique_admin(username, prjname):
    tmpl = PrjRole.objects.filter(project__projectname = prjname)
    adm_list = tmpl.values_list('registration__username', flat = True).distinct()
    if len(adm_list) != 1:
        return False
    return username in adm_list

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


class AAIDBRouter:

    AAIDB_NAME = 'cloudvenetoaai'

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'openstack_auth_shib':
            return AAIDBRouter.AAIDB_NAME
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'openstack_auth_shib':
            return AAIDBRouter.AAIDB_NAME
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label == 'openstack_auth_shib':
            return True
        if obj2._meta.app_label == 'openstack_auth_shib':
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'openstack_auth_shib':
            return db == AAIDBRouter.AAIDB_NAME
        return None


def getProjectInfo(request, project):
    result = {
        'name' : project.projectname,
        'descr' : project.description,
        'comp_required' : False,
        'exp_date' : None
    }

    comp_rules = getattr(settings, 'COMPLIANCE_RULES', None)
    if not comp_rules:
        return result

    if NEW_MODEL:
        # no transactions here
        for attr in PrjAttribute.objects.filter(project = project):

            if attr.name == ATT_PRJ_ORG:
                for o_item in comp_rules.get('organizations', []):
                    if o_item == attr.value:
                        result['comp_required'] = True

            elif attr.name == ATT_PRJ_CIDR:
                for n_item in comp_rules.get('subnets', []):
                    if attr.value.startswith(n_item):
                        result['comp_required'] = True

            elif attr.name == ATT_PRJ_EXP:
                result['exp_date'] = datetime.fromisoformat(attr.value)
        return result

    try:
        kprj_man = keystone_api.keystoneclient(request).projects
        for item in comp_rules.get('organizations', []):
            if ('O=' + item) in kprj_man.list_tags(project.projectid):
                result['comp_required'] = True
    except:
        LOG.error("Registration error", exc_info=True)
        result['err_msg'] = _("Cannot retrieve organization tag")

    try:
        for s_item in neutron_api.subnet_list(request, project_id = project.projectid):
            for p_item in comp_rules.get('subnets', []):
                if p_item in s_item.cidr:
                    result['comp_required'] = True
    except:
        LOG.error("Registration error", exc_info=True)
        result['err_msg'] = _("Cannot retrieve subnetwork")

    return result

