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
import logging.config
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

LOG = logging.getLogger("cronscript_utils")

def build_option_list():
    return BaseCommand.option_list + (
        make_option('--config',
            dest='conffile',
            action='store',
            default=None,
            help='The configuration file for this plugin'
        ),
        make_option('--logconf',
            dest='logconffile',
            action='store',
            default=None,
            help='The configuration file for the logging system'
        ),
    )

def get_prjman_roleid(keystone):
    role_name = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
    
    for tmp_role in keystone.roles.list():
        if tmp_role.name == role_name:
            return tmp_role.id
    raise CommandError("Cannot retrieve project manager role id")

def configure_log(options):
    logconffile = options.get('logconffile', None)
    if logconffile:
        logging.config.fileConfig(logconffile)

class ConfigBin:
    def __init__(self):
        self.cron_user = getattr(settings, 'CRON_USER', 'admin')
        self.cron_pwd = getattr(settings, 'CRON_PWD', '')
        self.cron_prj = getattr(settings, 'CRON_PROJECT', 'admin')
        self.cron_domain = getattr(settings, 'CRON_DOMAIN', 'Default')
        self.cron_ca = getattr(settings, 'OPENSTACK_SSL_CACERT', '')
        self.cron_kurl = getattr(settings, 'OPENSTACK_KEYSTONE_URL', '')
        self.cron_renewd = getattr(settings, 'CRON_RENEW_DAYS', 30)
        self.cron_defer = getattr(settings, 'CRON_DEFER_DAYS', 0)
        self.cron_plan = getattr(settings, 'NOTIFICATION_PLAN', None)

def readParameters(conffile):
    result = dict()

    cfile = None
    try:
        cfile = open(conffile)
        for line in cfile:
            tmps = line.strip()
            if len(tmps) == 0 or tmps.startswith('#'):
                continue
        
            tmpl = tmps.split('=')
            if len(tmpl) == 2:
                result[tmpl[0].strip()] = tmpl[1].strip()
    except:
        LOG.error("Cannot parse configuration file", exc_info=True)
    
    if cfile:
        cfile.close()
    
    return result

def configure_app(options):
    result = ConfigBin()

    conffile = options.get('conffile', None)
    if conffile:
        params = readParameters(conffile)

        if len(params) == 0:
            return result

        result.cron_user = params['USERNAME']
        result.cron_pwd = params['PASSWD']
        result.cron_prj = params['TENANTNAME']
        result.cron_ca = params.get('CAFILE','')
        result.cron_domain = params.get('DOMAIN', 'Default')
        result.cron_kurl = params['AUTHURL']
        result.cron_renewd = int(params.get('RENEW_DAYS', '30'))
        result.cron_defer = int(params.get('DEFER_DAYS', '0'))
        result.cron_plan = params.get('NOTIFICATION_PLAN', None)

    return result

def build_contact_list():
    return getattr(settings, 'MANAGERS', None)

