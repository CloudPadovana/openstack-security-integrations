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
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import PSTATUS_RENEW_ATTEMPT
from openstack_auth_shib.models import PSTATUS_RENEW_DISC

from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import PROPOSED_RENEWAL

from horizon.management.commands.cronscript_utils import CloudVenetoCommand

LOG = logging.getLogger("renewalrequest")

class Command(CloudVenetoCommand):

    def handle(self, *args, **options):

        super(Command, self).handle(options)

        now = datetime.now(timezone.utc)
        exp_date = now + timedelta(self.config.cron_renewd)

        LOG.info("Checking for renewal after %s" % str(exp_date))

        try:

            new_reqs = dict()
            mail_table = dict()

            with transaction.atomic():

                stored_reqs = set()
                renew_status_list = [
                    PSTATUS_RENEW_ADMIN,
                    PSTATUS_RENEW_MEMB,
                    PSTATUS_RENEW_ATTEMPT,
                    PSTATUS_RENEW_DISC
                ]
                for prj_req in PrjRequest.objects.filter(flowstatus__in=renew_status_list):
                    stored_reqs.add((prj_req.registration.regid, prj_req.project.projectname))

                for e_item in Expiration.objects.filter(expdate__lte=exp_date, expdate__gt=now):

                    regid = e_item.registration.regid
                    if not (regid, e_item.project.projectname) in stored_reqs:

                        if not regid in mail_table:
                            tmpobj = EMail.objects.filter(registration=e_item.registration)
                            mail_table[regid] = tmpobj[0].email if len(tmpobj) else None

                        f_exp = e_item.expdate.date().isoformat()

                        new_reqs[(e_item.registration, e_item.project)] = (mail_table[regid], f_exp)

                for req_pair, req_data in new_reqs.items():
                    reqArgs = {
                        'registration' : req_pair[0],
                        'project' : req_pair[1],
                        'notes' : req_data[1],
                        'flowstatus' : PSTATUS_RENEW_ATTEMPT
                    }
                    PrjRequest(**reqArgs).save()

                    LOG.info("Issued proposed renewal for %s" % req_pair[0].username)

            for req_pair, req_data in new_reqs.items():
                try:
                    noti_params = {
                        'username' : req_pair[0].username,
                        'project' : req_pair[1].projectname
                    }
                    notifyUser(req_data[0], PROPOSED_RENEWAL, noti_params,
                               project_id=req_pair[1].projectid,
                               dst_user_id=req_pair[0].userid)
                except:
                    LOG.error("Cannot notify %s" % req_pair[0].username, exc_info=True)
        except:
            LOG.error("Proposed renewal failed", exc_info=True)
            raise CommandError("Proposed renewal failed")

