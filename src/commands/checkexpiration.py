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

from datetime import datetime, timedelta, timezone

from django.db import transaction
from django.core.management.base import CommandError
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole

from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import USER_EXPIRED_TYPE
from openstack_auth_shib.notifications import DEL_USERS_SUMMARY

from horizon.management.commands.cronscript_utils import CloudVenetoCommand
from horizon.management.commands.cronscript_utils import get_prjman_roleid

from keystoneclient.v3 import client

LOG = logging.getLogger("checkexpiration")

class Command(CloudVenetoCommand):

    def handle(self, *args, **options):
    
        super(Command, self).handle(options)
        
        LOG.info("Checking expired users")
        try:

            keystone_client = client.Client(username=self.config.cron_user,
                                            password=self.config.cron_pwd,
                                            project_name=self.config.cron_prj,
                                            user_domain_name=self.config.cron_domain,
                                            project_domain_name=self.config.cron_domain,
                                            cacert=self.config.cron_ca,
                                            auth_url=self.config.cron_kurl)

            prjman_roleid = get_prjman_roleid(keystone_client)
            cloud_adminid = keystone_client.auth_ref.user_id

        except:
            LOG.error("Check expiration failed", exc_info=True)
            raise CommandError("Check expiration failed")

        exp_date = datetime.now(timezone.utc) - timedelta(self.config.cron_defer)

        summary_list = list()

        for mem_item in Expiration.objects.filter(expdate__lt=exp_date):

            username = mem_item.registration.username
            userid = mem_item.registration.userid
            prjname = mem_item.project.projectname
            prjid = mem_item.project.projectid

            is_last_admin = False

            try:
                with transaction.atomic():

                    tmpres = EMail.objects.filter(registration=mem_item.registration)
                    user_mail = tmpres[0].email if len(tmpres) else None

                    q_args = {
                        'registration' : mem_item.registration,
                        'project' : mem_item.project
                    }

                    Expiration.objects.delete_expiration(**q_args)

                    PrjRequest.objects.filter(**q_args).delete()

                    n_del, dummy_d = PrjRole.objects.filter(**q_args).delete()
                    if n_del > 0:
                        is_last_admin = (PrjRole.objects.filter(project = mem_item.project).count() == 0)

                    arg_dict = { 'project' : prjid, 'user' : userid }
                    for r_item in keystone_client.role_assignments.list(**arg_dict):
                        keystone_client.roles.revoke(r_item.role['id'], **arg_dict)

                    summary_list.append((username, user_mail, prjname, is_last_admin))
                    LOG.info("Removed %s from %s" % (username, prjid))
            except:
                LOG.error("Check expiration failed for %s" % username, exc_info=True)

            try:
                if is_last_admin:
                    keystone_client.roles.grant(prjman_roleid, user=cloud_adminid, project=prjid)
                    LOG.info("Cloud Administrator as admin for %s" % prjid)
            except:
                LOG.error("Cannot set super admin for project %s" % prjname, exc_info=True)

            try:
                noti_params = { 'username' : username, 'project' : prjname }
                notifyUser(user_mail, USER_EXPIRED_TYPE, noti_params,
                           project_id=prjid, dst_user_id=userid)
            except:
                LOG.error("Cannot send notification for expired user %s" % username, exc_info=True)

        if len(summary_list) > 0:
            try:
                noti_params = { 'summary' : summary_list }
                notifyAdmin(DEL_USERS_SUMMARY, noti_params)
            except:
                LOG.error("Cannot send summary", exc_info=True)

