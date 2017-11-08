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
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB

from openstack_auth_shib.notifications import notifyProject
from openstack_auth_shib.notifications import USER_NEED_RENEW

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app

LOG = logging.getLogger("renewalrequest")

class Command(BaseCommand):

    option_list = build_option_list()

    def handle(self, *args, **options):

        configure_log(options)

        config = configure_app(options)

        now = datetime.now()
        exp_date = now + timedelta(config.cron_renewd)

        LOG.info("Checking for renewal after %s" % str(exp_date))

        try:

            new_reqs = dict()
            mail_table = dict()

            with transaction.atomic():

                stored_reqs = set()
                renew_status_list = [ PSTATUS_RENEW_ADMIN, PSTATUS_RENEW_MEMB ]
                for prj_req in PrjRequest.objects.filter(flowstatus__in=renew_status_list):
                    stored_reqs.add((prj_req.registration.regid, prj_req.project.projectname))

                for e_item in Expiration.objects.filter(expdate__lte=exp_date, expdate__gt=now):

                    if not (e_item.registration.regid, e_item.project.projectname) in stored_reqs:
                        q_args = {
                            'registration' : e_item.registration,
                            'project' : e_item.project
                        }
                        is_admin = (PrjRole.objects.filter(**q_args).count() > 0)
                        new_reqs[(e_item.registration, e_item.project)] = is_admin

                for req_pair, is_admin in new_reqs.items():
                    reqArgs = {
                        'registration' : req_pair[0],
                        'project' : req_pair[1],
                        'flowstatus' : PSTATUS_RENEW_ADMIN if is_admin else PSTATUS_RENEW_MEMB
                    }
                    PrjRequest(**reqArgs).save()

                    LOG.info("Issued renewal for %s" % req_pair[0].username)

                    if mail_table.has_key(req_pair[1].projectname):
                        continue

                    tmpl = list()
                    for prj_role in PrjRole.objects.filter(project=req_pair[1]):
                        tmpobj = EMail.objects.filter(registration=prj_role.registration)
                        if len(tmpobj):
                            tmpl.append(tmpobj[0].email)
                    mail_table[req_pair[1].projectname] = tmpl

            for req_pair, is_admin in new_reqs.items():
                try:
                    noti_params = {
                        'username' : req_pair[0].username,
                        'project' : req_pair[1].projectname
                    }
                    notifyProject(mail_table[req_pair[1].projectname], USER_NEED_RENEW, noti_params,
                                  user_id=req_pair[0].userid, project_id=req_pair[1].projectid,
                                  dst_project_id=req_pair[1].projectid)
                except:
                    LOG.error("Cannot notify %s" % req_pair[0].username, exc_info=True)
        except:
            LOG.error("Renewal request failed", exc_info=True)
            raise CommandError("Renewal request failed")

