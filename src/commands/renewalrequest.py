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
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import get_prjman_roleid
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app

from keystoneclient.v3 import client

LOG = logging.getLogger("renewalrequest")

class Command(BaseCommand):

    option_list = build_option_list()
        
    def handle(self, *args, **options):
    
        configure_log(options)
        
        config = configure_app(options)
        
        try:

            now = datetime.now()
            exp_date = now + timedelta(config.cron_renewd)

            LOG.info("Checking for renewal after %s" % str(exp_date))
            
            keystone_client = client.Client(username=config.cron_user,
                                            password=config.cron_pwd,
                                            project_name=config.cron_prj,
                                            user_domain_name=config.cron_domain,
                                            project_domain_name=config.cron_domain,
                                            cacert=config.cron_ca,
                                            auth_url=config.cron_kurl)
                            
            q_args = {
                'expdate__lte' : exp_date,
                'expdate__gt' : now
            }
            exp_members = Expiration.objects.filter(**q_args)

            prjman_roleid = get_prjman_roleid(keystone_client)

        except:
            LOG.error("Request for renewal failed", exc_info=True)
            raise CommandError("Request for renewal failed")

        with transaction.atomic():

            
            for e_item in exp_members:
                #
                # TODO check API
                #
                try:
                    is_prj_admin = keystone_client.roles.check(prjman_roleid,
                        e_item.registration.userid,
                        None, None,
                        e_item.project.projectid)
                except:
                     is_prj_admin = False 
                    
                try:

                    q_args = {
                        'registration' : e_item.registration,
                        'project' : e_item.project,
                        'flowstatus__in' : [ PSTATUS_RENEW_ADMIN, PSTATUS_RENEW_MEMB ]
                    }
                    if len(PrjRequest.objects.filter(**q_args)) == 0:

                        reqArgs = {
                            'registration' : e_item.registration,
                            'project' : e_item.project,
                            'flowstatus' : PSTATUS_RENEW_ADMIN if is_prj_admin
                                                            else PSTATUS_RENEW_MEMB
                        }
                        PrjRequest(**reqArgs).save()
                        
                        LOG.info("Issued renewal for %s" % e_item.registration.username)

                except:
                    LOG.error("Check expiration failed for", exc_info=True)
                    raise CommandError("Check expiration failed")


