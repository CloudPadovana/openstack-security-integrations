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

from datetime import datetime, timedelta
from optparse import make_option

from django.conf import settings
from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB

from keystoneclient.v3 import client

LOG = logging.getLogger("checkexpiration")

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
    
    #
    # TODO move in a common module
    #
    def get_prjman_roleid(self, keystone):
        role_name = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')
        
        for tmp_role in keystone.roles.list():
            if tmp_role.name == role_name:
                return tmp_role.id
        raise CommandError("Cannot retrieve project manager role id")
    
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
            cron_renewd = getattr(settings, 'CRON_RENEW_DAYS', 30)
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
            cron_renewd = int(params.get('RENEW_DAYS', '30'))
            
        try:

            now = datetime.now()
            exp_date = now + timedelta(cron_renewd)

            LOG.info("Checking for renewal after %s" % str(exp_date))
            
            keystone_client = client.Client(username=cron_user,
                                            password=cron_pwd,
                                            project_name=cron_prj,
                                            cacert=cron_ca,
                                            auth_url=cron_kurl)
                            
            q_args = {
                'expdate__lte' : exp_date,
                'expdate__gt' : now
            }
            exp_members = Expiration.objects.filter(**q_args)

            prjman_roleid = self.get_prjman_roleid(keystone_client)

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


