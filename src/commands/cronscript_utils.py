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

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

LOG = logging.getLogger("cronscript_utils")

class CloudVenetoCommand(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--config',
                            dest='conffile',
                            action='store',
                            default=None,
                            help='The configuration file for this plugin')
        parser.add_argument('--logconf',
                            dest='logconffile',
                            action='store',
                            default=None,
                            help='The configuration file for the logging system')

    def handle(self, options):

        logconffile = options.get('logconffile', None)
        if logconffile:
            logging.config.fileConfig(logconffile)

        self.config = ConfigBin()

        conffile = options.get('conffile', None)
        if conffile:
            params = self._readParameters(conffile)

            if len(params) > 0:
                self.config.cron_user = params['USERNAME']
                self.config.cron_pwd = params['PASSWD']
                self.config.cron_prj = params['TENANTNAME']
                self.config.cron_ca = params.get('CAFILE','')
                self.config.cron_domain = params.get('DOMAIN', 'Default')
                self.config.cron_kurl = params['AUTHURL']
                self.config.cron_renewd = int(params.get('RENEW_DAYS', '30'))
                self.config.cron_defer = int(params.get('DEFER_DAYS', '0'))
                self.config.cron_plan = params.get('NOTIFICATION_PLAN', None)

    def _readParameters(self, conffile):
        result = dict()

        try:
            with open(conffile) as cfile:
                for line in cfile:
                    tmps = line.strip()
                    if len(tmps) == 0 or tmps.startswith('#'):
                        continue

                    tmpl = tmps.split('=')
                    if len(tmpl) == 2:
                        result[tmpl[0].strip()] = tmpl[1].strip()
        except:
            LOG.error("Cannot parse configuration file", exc_info=True)

        return result


def get_prjman_roleid(keystone):
    role_name = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
    
    for tmp_role in keystone.roles.list():
        if tmp_role.name == role_name:
            return tmp_role.id
    raise CommandError("Cannot retrieve project manager role id")

class ConfigBin:
    def __init__(self):
        script_params = getattr(settings, 'SCRIPT_PARAMETERS', {})

        self.cron_user = script_params.get('CRON_USER', 'admin')
        self.cron_pwd = script_params.get('CRON_PWD', '')
        self.cron_prj = script_params.get('CRON_PROJECT', 'admin')
        self.cron_domain = script_params.get('CRON_DOMAIN', 'Default')
        self.cron_ca = script_params.get('OPENSTACK_SSL_CACERT', '')
        self.cron_kurl = script_params.get('OPENSTACK_KEYSTONE_URL', '')
        self.cron_renewd = script_params.get('CRON_RENEW_DAYS', 30)
        self.cron_defer = script_params.get('CRON_DEFER_DAYS', 0)
        self.cron_plan = script_params.get('NOTIFICATION_PLAN', None)
        self.key_path = script_params.get('PRIVATE_KEY_PATH', None)
        self.gate_user = script_params.get('GATE_USER', 'root')
        self.gate_address = script_params.get('GATE_ADDRESS', None)
        self.ban_script = script_params.get('GATE_BAN_SCRIPT', None)
        self.allow_script = script_params.get('GATE_ALLOW_SCRIPT', None)

def build_contact_list():
    return getattr(settings, 'MANAGERS', None)

