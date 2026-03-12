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

from keystoneclient.v3.client import Client as KeystoneClient
from novaclient.client import Client as NovaClient
from cinderclient.client import Client as CinderClient

LOG = logging.getLogger("cronscript_utils")

class CloudVenetoCommand(BaseCommand):

    def __init__(self):
        super(CloudVenetoCommand, self).__init__()
        self.keystone_client = None
        self.nova_client = None
        self.cinder_client = None
        
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

        self.config = ConfigBin(options.get('conffile', None))

    def get_keystone_client(self):
        if self.keystone_client:
            return self.keystone_client
        try:
            self.keystone_client = KeystoneClient(username = self.config.cron_user,
                                                  password = self.config.cron_pwd,
                                                  project_name = self.config.cron_prj,
                                                  user_domain_name = self.config.cron_domain,
                                                  project_domain_name = self.config.cron_domain,
                                                  cacert = self.config.cron_ca,
                                                  auth_url = self.config.cron_kurl)
            return self.keystone_client
        except:
            LOG.error("Keystone connection failed", exc_info=True)
        raise CommandError("Keystone connection failed")

    def get_nova_client(self):
        if self.nova_client:
            return self.nova_client
        try:
            self.nova_client = NovaClient('2',
                                          username = self.config.cron_user,
                                          password = self.config.cron_pwd,
                                          project_name = self.config.cron_prj,
                                          user_domain_name = self.config.cron_domain,
                                          project_domain_name = self.config.cron_domain,
                                          cacert = self.config.cron_ca,
                                          auth_url = self.config.cron_kurl)
            return self.nova_client
        except:
            LOG.error("Nova connection failed", exc_info=True)
        raise CommandError("Nova connection failed")

    def get_cinder_client(self):
        if self.cinder_client:
            return self.cinder_client
        try:
            self.cinder_client = CinderClient('3', self.config.cron_user,
                                              self.config.cron_pwd, self.config.cron_prj,
                                              self.config.cron_kurl,
                                              cacert = self.config.cron_ca)
            return self.cinder_client
        except:
            LOG.error("Cinder connection failed", exc_info=True)
        raise CommandError("Cinder connection failed")

    def get_user_resources(self, userid, prjid):
        nova_client = self.get_nova_client()
        q_args1 = { 'user' : userid, 'project_id' : prjid, 'all_tenants' : True }
        servers = nova_client.servers.list(True, q_args1)

        cinder_client = self.get_cinder_client()
        q_args2 = { 'user_id' : userid, 'project_id' : prjid, 'all_tenants' : True }
        volumes = cinder_client.volumes.list(search_opts = q_args2)

        return (servers, volumes)

def get_prjman_roleid(keystone):
    role_name = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
    
    for tmp_role in keystone.roles.list():
        if tmp_role.name == role_name:
            return tmp_role.id
    raise CommandError("Cannot retrieve project manager role id")

class ConfigBin:
    def __init__(self, conffile = None):
        self.script_params = getattr(settings, 'SCRIPT_PARAMETERS', {})

        # TODO remove script-specific parameters
        self.cron_user = self.script_params.get('CRON_USER', 'admin')
        self.cron_pwd = self.script_params.get('CRON_PWD', '')
        self.cron_prj = self.script_params.get('CRON_PROJECT', 'admin')
        self.cron_domain = self.script_params.get('CRON_DOMAIN', 'Default')
        self.cron_ca = self.script_params.get('OPENSTACK_SSL_CACERT', '')
        self.cron_kurl = self.script_params.get('OPENSTACK_KEYSTONE_URL', '')
        self.cron_renewd = self.script_params.get('CRON_RENEW_DAYS', 30)
        self.cron_defer = self.script_params.get('CRON_DEFER_DAYS', 0)
        self.cron_plan = self._parse_cron_plan(self.script_params.get('NOTIFICATION_PLAN', None))
        self.key_path = self.script_params.get('PRIVATE_KEY_PATH', None)
        self.gate_user = self.script_params.get('GATE_USER', 'root')
        self.gate_address = self.script_params.get('GATE_ADDRESS', None)
        self.ban_script = self.script_params.get('GATE_BAN_SCRIPT', None)
        self.allow_script = self.script_params.get('GATE_ALLOW_SCRIPT', None)
        self.gate_dry_run = self.script_params.get('GATE_DRY_RUN', False)

        if conffile:
            params = self._readParameters(conffile)

            if len(params) > 0:
                self.cron_user = params['USERNAME']
                self.cron_pwd = params['PASSWD']
                self.cron_prj = params['TENANTNAME']
                self.cron_ca = params.get('CAFILE','')
                self.cron_domain = params.get('DOMAIN', 'Default')
                self.cron_kurl = params['AUTHURL']
                self.cron_renewd = int(params.get('RENEW_DAYS', '30'))
                self.cron_defer = int(params.get('DEFER_DAYS', '0'))
                self.cron_plan = self._parse_cron_plan(params.get('NOTIFICATION_PLAN', None))

                for name, value in params.items():
                    self.script_params[name] = value

    def _parse_cron_plan(self, plan_str):
        if plan_str:
            try:
                result = list()
                for tok in plan_str.split(','):
                    result.append(int(tok.strip()))
                return sorted(result)
            except:
                LOG.error("Cannot parse notification plan, default used", exc_info=True)

        return [ 5, 10, 20 ]
        
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

    def get(self, name, default):
        self.script_params.get(name, default)

def build_contact_list():
    return getattr(settings, 'MANAGERS', None)



