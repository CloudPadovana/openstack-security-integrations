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
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.notifications import notification_render
from openstack_auth_shib.notifications import notify as notifyUsers
from openstack_auth_shib.notifications import SUBSCR_REMINDER

from keystoneclient.v3 import client
from keystoneclient.v3.role_assignments import RoleAssignmentManager

LOG = logging.getLogger("pendingsubscr")

class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
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
    
    def __init__(self):
        super(Command, self).__init__()
        self.email_table = dict()
    
    def readParameters(self, conffile):
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
    
    def get_prjman_roleid(self, keystone):
        role_name = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
        
        for tmp_role in keystone.roles.list():
            if tmp_role.name == role_name:
                return tmp_role.id
        raise CommandError("Cannot retrieve project manager role id")
    
    def get_email(self, keystone, u_id, registr):
    
        if u_id:
            if not u_id in self.email_table:
                try:
                    tmp_email = keystone.users.get(u_id).email
                    if tmp_email:
                        self.email_table[u_id] = tmp_email
                except:
                    LOG.error("Keystone call failed", exc_info=True)
            if u_id in self.email_table:
                return self.email_table[u_id]

        if registr:
            if not registr.regid in self.email_table:
                try:
                    tmpItems = RegRequest.objects.filter(registration=registr)
                    if len(tmpItems) > 0:
                        self.email_table[registr.regid] = tmpItems[0].email
                except:
                    LOG.error("Query failed", exc_info=True)
            if registr.regid in self.email_table:
                return self.email_table[registr.regid]
        
        return None
    
    def handle(self, *args, **options):
    
        logconffile = options.get('logconffile', None)
        if logconffile:
            logging.config.fileConfig(logconffile)
        
        conffile = options.get('conffile', None)
        if not conffile:
            cron_user = getattr(settings, 'CRON_USER', 'admin')
            cron_pwd = getattr(settings, 'CRON_PWD', '')
            cron_prj = getattr(settings, 'CRON_PROJECT', 'admin')
            cron_ca = getattr(settings, 'OPENSTACK_SSL_CACERT', '')
            cron_kurl = getattr(settings, 'OPENSTACK_KEYSTONE_URL', '')
        else:
            params = self.readParameters(conffile)
            # Empty conf file used in rpm
            if len(params) == 0:
                return

            cron_user = params['USERNAME']
            cron_pwd = params['PASSWD']
            cron_prj = params['TENANTNAME']
            cron_ca = params.get('CAFILE','')
            cron_kurl = params['AUTHURL']
            
        try:
            
            keystone_client = client.Client(username=cron_user,
                                            password=cron_pwd,
                                            project_name=cron_prj,
                                            cacert=cron_CA,
                                            auth_url=cron_kurl)
            
            req_table = dict()
            prj_res_table = dict()
            for p_req in PrjRequest.objects.filter(flowstatus=PSTATUS_PENDING):
                if not p_req.project.projectid in req_table:
                    req_table[p_req.project.projectid] = list()
                uname = p_req.registration.username
                email = self.get_email(None, None, p_req.registration)
                req_table[p_req.project.projectid].append((uname, email))
                prj_res_table[p_req.project.projectid] = p_req.project.projectname
            
            admin_table = dict()
            prjman_roleid = self.get_prjman_roleid(keystone_client)
            for prj_id in req_table:
                q_args = {
                    'scope.project.id' : prj_id,
                    'role.id' : prjman_roleid
                }
                
                for assign in super(RoleAssignmentManager, keystone_client.role_assignments).list(**q_args):
                
                    email = self.get_email(keystone_client, assign.user['id'], None)
                    
                    if not email in admin_table:
                        admin_table[email] = list()
                    admin_table[email].append(prj_id)
                    
            for email in admin_table:
                for prj_id in admin_table[email]:
                    noti_params = {
                        'pendingreqs' : req_table[prj_id],
                        'project' : prj_res_table[prj_id]
                    }
                    noti_sbj, noti_body = notification_render(SUBSCR_REMINDER, noti_params)
                    notifyUsers(email, noti_sbj, noti_body)
                
        except:
            LOG.error("Notification failed", exc_info=True)
            raise CommandError("Notification failed")


