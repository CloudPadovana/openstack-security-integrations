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

from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import Expiration

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app

from keystoneclient.v3 import client

LOG = logging.getLogger("populatexpiration")

class Command(BaseCommand):

    option_list = build_option_list()

    def handle(self, *args, **options):
    
        configure_log(options)
        
        config = configure_app(options)

        try:
        
            prj_dict = dict()
            
            for prj_item in Project.objects.all():
                if prj_item.projectid:
                    prj_dict[prj_item.projectid] = prj_item

            keystone_client = client.Client(username=config.cron_user,
                                            password=config.cron_pwd,
                                            project_name=config.cron_prj,
                                            cacert=config.cron_ca,
                                            auth_url=config.cron_kurl)

            with transaction.atomic():
                for reg_user in Registration.objects.all():
                
                    if not reg_user.userid:
                        LOG.info("Skipped unregistered user %s" % reg_user.username)
                        continue
                    
                    for r_item in keystone_client.role_assignments.list(user=reg_user.userid):
                        if not r_item.scope['project']['id'] in prj_dict:
                            LOG.info("Skipped unregistered project %s for %s" % \
                            (r_item.scope['project']['id'], reg_user.username))
                        curr_prj = prj_dict[r_item.scope['project']['id']]
                        
                        prj_exp = Expiration()
                        prj_exp.registration = reg_user
                        prj_exp.project = curr_prj
                        prj_exp.expdate = reg_user.expdate
                        prj_exp.save()
                        
                        LOG.info("Imported expiration for %s in %s: %s" % \
                        (reg_user.username, curr_prj.projectname, \
                        reg_user.expdate.strftime("%A, %d. %B %Y %I:%M%p")))

        except:
            LOG.error("Import failed", exc_info=True)
            raise CommandError("Import failed")

