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

from datetime import datetime
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.notifications import notification_render
from openstack_auth_shib.notifications import notify as notifyUsers
from openstack_auth_shib.notifications import USER_EXP_TYPE

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app
from horizon.management.commands.cronscript_utils import build_contact_list

from keystoneclient.v3 import client

LOG = logging.getLogger("notifyexpiration")

class Command(BaseCommand):

    option_list = build_option_list()
    
    def _get_days_to_exp(self, n_plan):
        result = list()
        
        if n_plan:
            try:
                for tok in n_plan.split(','):
                    result.append(int(tok.strip()))
            except:
                LOG.error("Cannot parse notification plan, default used", exc_info=True)
                
        if len(result) == 0:
            result.append(5)
            result.append(10)
            result.append(20)
        return result
    
    def handle(self, *args, **options):
    
        configure_log(options)
        
        config = configure_app(options)
                    
        try:
            
            now = datetime.now()
            contact_list = build_contact_list()
            
            for days_to_exp in self._get_days_to_exp(config.cron_plan):
                
                tframe = now + timedelta(days=days_to_exp)
                
                q_args = {
                    'expdate__gte' : tframe.replace(hour=0, minute=0, second=0, microsecond=0),
                    'expdate__lte' : tframe.replace(hour=23, minute=59, second=59, microsecond=999999)
                }
            
                for exp_item in Expiration.objects.filter(**q_args):
                    try:
                        
                        keystone = client.Client(username=config.cron_user,
                                                 password=config.cron_pwd,
                                                 project_name=config.cron_prj,
                                                 cacert=config.cron_ca,
                                                 auth_url=config.cron_kurl)
                        
                        tmpuser = keystone.users.get(exp_item.registration.userid)
                        
                        
                        noti_params = {
                            'username' : exp_item.registration.username,
                            'days' : days_to_exp,
                            'contacts' : contact_list
                        }
                        noti_sbj, noti_body = notification_render(USER_EXP_TYPE, noti_params)
                        notifyUsers(tmpuser.email, noti_sbj, noti_body)
                        
                        #
                        # TODO send notification to project admins
                        #
                        
                    except:
                        LOG.warning("Cannot notify %s" % exp_item.registration.username, exc_info=True)
                
        except:
            LOG.error("Notification failed", exc_info=True)
            raise CommandError("Notification failed")


