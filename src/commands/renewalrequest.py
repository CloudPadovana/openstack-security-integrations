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
from optparse import make_option

from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

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
    
    def handle(self, *args, **options):
    
        logconffile = options.get('logconffile', None)
        if logconffile:
            logging.config.fileConfig(logconffile)
        
        conffile = options.get('conffile', None)
        if not conffile:
            logging.error("Missing configuration file")
            raise CommandError("Missing configuration file\n")
            
        try:
            params = self.readParameters(conffile)
            
            # Empty conf file used in rpm
            if len(params) == 0:
                return
            
            dtime = timedelta(int(params.get('RENEW_DAYS', '30')))
            now = datetime.now()
            exp_date = now - dtime
            LOG.info("Checking expiration dates before %s" % str(exp_date))
            
            keystone = client.Client(username=params['USERNAME'],
                                     password=params['PASSWD'],
                                     project_name=params['TENANTNAME'],
                                     cacert=params.get('CAFILE',''),
                                     auth_url=params['AUTHURL'])
                            
            with transaction.atomic():
            
                q_args = {
                    'expdate__lt' : exp_date,
                    'expdate__ge' : now
                }
                for expiring_reg in Registration.objects.filter(**q_args):

                    for assign_obj in keystone.role_assignments.list(expiring_reg.userid):
                        project_name = None     # TODO
                        is_prj_admin = False    # TODO
                        if is_prj_admin:
                            flowstatus = PSTATUS_RENEW_ADMIN
                        else:
                            flowstatus = PSTATUS_RENEW_MEMB
                        
                        #
                        # TODO Use cache for projects
                        #
                        project = Project.objects.get(projectname=project_name)
                        
                        #
                        # TODO Check if request already exists
                        #
                        reqArgs = {
                            'registration' : expiring_reg,
                            'project' : project,
                            'flowstatus' : flowstatus,
                            'notes' : _('Request for renewal')
                        }
                        
                        PrjRequest(**reqArgs).save()


        except:
            LOG.error("Check expiration failed", exc_info=True)
            raise CommandError("Check expiration failed")


