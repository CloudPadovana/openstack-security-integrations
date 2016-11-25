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
            logging.error("Missing configuration file")
            raise CommandError("Missing configuration file\n")
            
        params = self.readParameters(conffile)
        
        # Empty conf file used in rpm
        if len(params) == 0:
            return

        LOG.info("Checking expired users")
        try:

            keystone_client = client.Client(username=params['USERNAME'],
                                            password=params['PASSWD'],
                                            project_name=params['TENANTNAME'],
                                            cacert=params.get('CAFILE',''),
                                            auth_url=params['AUTHURL'])

            dtime = timedelta(int(params.get('DEFER_DAYS', '0')))
            exp_date = datetime.now() - dtime
            exp_members = Expiration.objects.filter(expdate__lt=exp_date)

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
        
        prjman_roleid = self.get_prjman_roleid(keystone_client)
        cloud_adminid = keystone_client.auth_ref.user_id

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

