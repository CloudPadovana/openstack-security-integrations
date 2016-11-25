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
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import Registration
from openstack_auth_shib.notifications import notification_render
from openstack_auth_shib.notifications import notify as notifyUsers
from openstack_auth_shib.notifications import USER_EXP_TYPE

from keystoneclient.v3 import client

LOG = logging.getLogger("notifyexpiration")

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
            cron_plan = getattr(settings, 'NOTIFICATION_PLAN', None)
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
            cron_plan = params.get('NOTIFICATION_PLAN', None)
            
        try:
            
            now = datetime.now()
            contact_list = getattr(settings, 'MANAGERS', None)      
            
            for days_to_exp in self._get_days_to_exp(cron_plan):
                
                tframe = now + timedelta(days=days_to_exp)
                tf1 = tframe.replace(hour=0, minute=0, second=0, microsecond=0)
                tf2 = tframe.replace(hour=23, minute=59, second=59, microsecond=999999)
                all_regs = Registration.objects.filter(expdate__gte=tf1)
                all_regs = all_regs.filter(expdate__lte=tf2)
            
                for reg_item in all_regs:
                    try:
                        
                        keystone = client.Client(username=cron_user,
                                                 password=cron_pwd,
                                                 project_name=cron_prj,
                                                 cacert=cron_ca,
                                                 auth_url=cron_kurl
                        
                        tmpuser = keystone.users.get(reg_item.userid)
                        
                        
                        noti_params = {
                            'username' : reg_item.username,
                            'days' : days_to_exp,
                            'contacts' : contact_list
                        }
                        noti_sbj, noti_body = notification_render(USER_EXP_TYPE, noti_params)
                        notifyUsers(tmpuser.email, noti_sbj, noti_body)
                        
                    except:
                        LOG.warning("Cannot notify %s" % reg_item.username, exc_info=True)
                
        except:
            LOG.error("Notification failed", exc_info=True)
            raise CommandError("Notification failed")


