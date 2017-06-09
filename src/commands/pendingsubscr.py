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

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import get_prjman_roleid
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app

from keystoneclient.v3 import client
from keystoneclient.v3.role_assignments import RoleAssignmentManager

LOG = logging.getLogger("pendingsubscr")

class Command(BaseCommand):

    option_list = build_option_list()
    
    def __init__(self):
        super(Command, self).__init__()
        self.email_table = dict()
    
    def get_email(self, keystone, u_id):
    
        if not u_id:
            return None

        if not u_id in self.email_table:
            try:
                tmp_email = keystone.users.get(u_id).email
                if tmp_email:
                    self.email_table[u_id] = tmp_email
            except:
                LOG.error("Keystone call failed", exc_info=True)

        if u_id in self.email_table:
            return self.email_table[u_id]

        return None
    
    def handle(self, *args, **options):
    
        configure_log(options)
        
        config = configure_app(options)
            
        try:
            
            keystone_client = client.Client(username=config.cron_user,
                                            password=config.cron_pwd,
                                            project_name=config.cron_prj,
                                            cacert=config.cron_ca,
                                            auth_url=config.cron_kurl)
            
            req_table = dict()
            prj_res_table = dict()
            for p_req in PrjRequest.objects.filter(flowstatus=PSTATUS_PENDING):
                curr_prjid = p_req.project.projectid
                if not curr_prjid in req_table:
                    req_table[curr_prjid] = list()
                req_table[curr_prjid].append(p_req.registration.username))
                prj_res_table[curr_prjid] = p_req.project.projectname
            
            admin_table = dict()
            prjman_roleid = get_prjman_roleid(keystone_client)
            for prj_id in req_table:
                q_args = {
                    'scope.project.id' : prj_id,
                    'role.id' : prjman_roleid
                }
                
                for assign in super(RoleAssignmentManager, keystone_client.role_assignments).list(**q_args):
                
                    email = self.get_email(keystone_client, assign.user['id'])
                    
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


