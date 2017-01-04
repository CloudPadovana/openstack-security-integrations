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

from datetime import datetime, timedelta

from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import PrjRequest

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import get_prjman_roleid
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app

from keystoneclient.v3 import client

LOG = logging.getLogger("checkexpiration")

class Command(BaseCommand):

    option_list = build_option_list()
    
    def handle(self, *args, **options):
    
        configure_log(options)
        
        config = configure_app(options)
        
        LOG.info("Checking expired users")
        try:

            keystone_client = client.Client(username=config.cron_user,
                                            password=config.cron_pwd,
                                            project_name=config.cron_prj,
                                            cacert=config.cron_ca,
                                            auth_url=config.cron_kurl)

            exp_date = datetime.now() - timedelta(config.cron_defer)
            exp_members = Expiration.objects.filter(expdate__lt=exp_date)

            prjman_roleid = get_prjman_roleid(keystone_client)
            cloud_adminid = keystone_client.auth_ref.user_id

        except:
            LOG.error("Check expiration failed", exc_info=True)
            raise CommandError("Check expiration failed")

        updated_prjs = set()

        for mem_item in exp_members:

            updated_prjs.add(mem_item.project.projectid)
            
            LOG.debug("Expired %s for %s" % \
                    (mem_item.registration.username, mem_item.project.projectname))
            
            try:
                with transaction.atomic():
                    
                    q_args = {
                        'registration' : mem_item.registration,
                        'project' : mem_item.project
                    }
                    Expiration.objects.filter(**q_args).delete()
                    PrjRequest.objects.filter(**q_args).delete()

                    arg_dict = {
                        'project' : mem_item.project.projectid,
                        'user' : mem_item.registration.userid
                    }
                    for r_item in keystone_client.role_assignments.list(**arg_dict):
                        keystone_client.roles.revoke(r_item.role['id'], **arg_dict)
                    
                    LOG.info("Removed %s from %s" %
                        (mem_item.registration.username, mem_item.project.projectid))

                #
                # TODO missing notification
                #                    

            except:
                LOG.error("Check expiration failed for %s" % mem_item.registration.username,
                            exc_info=True)

        #
        # Check for tenants without admin (use cloud admin if missing)
        #
        
        for prj_id in updated_prjs:
        
            try:
                url = '/role_assignments?scope.project.id=%s&role.id=%s'
                resp, body = keystone_client.get(url % (prj_id, prjman_roleid))
                
                if len(body['role_assignments']) == 0:
                    keystone_client.roles.grant(prjman_roleid,
                        user = cloud_adminid,
                        project = prj_id
                    )
                    LOG.info("Cloud Administrator as admin for %s" % prj_id)
            except:
                #
                # TODO notify error to cloud admin
                #
                LOG.error("No tenant admin for %s" % prj_id, exc_info=True)

