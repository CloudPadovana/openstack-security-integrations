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

import os, os.path
import logging
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app
from horizon.management.commands.cronscript_utils import build_contact_list

from keystoneclient.v3 import client

from openstack_auth_shib.notifications import notify as notifyUsers
from openstack_auth_shib.notifications import notification_render
from openstack_auth_shib.notifications import DEF_MSG_CACHE_DIR

LOG = logging.getLogger("notifybooked")

D_PATTERN = re.compile('^([^|]+)\|(.+)$')

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
CACHE_DIR = getattr(settings, 'MSG_CACHE_DIR', DEF_MSG_CACHE_DIR)

class Command(BaseCommand):

    option_list = build_option_list()
    
    def handle(self, *args, **options):
    
        configure_log(options)
        
        config = configure_app(options)
        
        prj_id_list = list()
        for item in os.listdir(CACHE_DIR):
            if not item.endswith('.tmp'):
                prj_id_list.append(item)
        if len(prj_id_list) == 0:
            return
        LOG.info("Detected booked notifications")

        try:

            keystone_client = client.Client(username=config.cron_user,
                                            password=config.cron_pwd,
                                            project_name=config.cron_prj,
                                            cacert=config.cron_ca,
                                            auth_url=config.cron_kurl)

            prjman_roleid = None
            for role in keystone_client.roles.list():
                if role.name == TENANTADMIN_ROLE:
                    prjman_roleid = role.id

        except:
            LOG.error("Notification failed", exc_info=True)
            raise CommandError("Notification failed: cannot contact Keystone")


        if not prjman_roleid:
            raise CommandError("Notification failed: project administrator undefined")
            
        for prj_id in prj_id_list:
        
            prj_emails = list()
            
            url = '/role_assignments?scope.project.id=%s&role.id=%s'
            resp, body = keystone_client.get(url % (prj_id, prjman_roleid))
            for item in body['role_assignments']:
                tntadmin = keystone_client.users.get(item['user']['id'])
                prj_emails.append(tntadmin.email)
            
            tmpprj = keystone_client.projects.get(prj_id)

            try:

                f_name = os.path.join(CACHE_DIR, prj_id)
                with open(f_name) as n_file:
                    for line in n_file.readlines():
                        rres = D_PATTERN.search(line)
                        if rres:
                            noti_params = {
                                'username' : rres.group(1),
                                'project' : tmpprj.name
                            }
                            noti_sbj, noti_body = notification_render(rres.group(2), noti_params)
                            for prj_email in prj_emails:
                                notifyUsers(prj_email, noti_sbj, noti_body)

                os.remove(f_name)

            except:
                LOG.error("Error reading %s" % f_name, exc_info=True)       




