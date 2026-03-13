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

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from django.core.management.base import CommandError
from django.db import transaction

from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PSTATUS_RENEW_ATTEMPT
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import USER_EXP_TYPE
from openstack_auth_shib.utils import get_prjadmin_emails

from horizon.management.commands.cronscript_utils import CloudVenetoCommand

LOG = logging.getLogger("notifyexpiration")

class Command(CloudVenetoCommand):

    def handle(self, *args, **options):

        super(Command, self).handle(options)

        try:

            now = datetime.now(timezone.utc)
            noti_table = dict()
            mail_table = dict()
            pmail_table = dict()

            with transaction.atomic():

                user_set = set()
                prj_set = set()
                candidates = [
                    x.registration for x in PrjRequest.objects.filter(flowstatus = PSTATUS_RENEW_ATTEMPT)
                ]

                counter = 0
                for days_to_exp in self.config.cron_plan:

                    tframe = now + timedelta(days=days_to_exp)
                    noti_table[days_to_exp] = list()

                    q_args = {
                        'registration__in' : candidates,
                        'expdate__gte' : tframe.replace(hour=0, minute=0, second=0, microsecond=0),
                        'expdate__lte' : tframe.replace(hour=23, minute=59, second=59, microsecond=999999)
                    }

                    for exp_item in Expiration.objects.filter(**q_args):

                        username = exp_item.registration.username
                        userid = exp_item.registration.userid
                        prjname = exp_item.project.projectname
                        prjid = exp_item.project.projectid

                        noti_table[days_to_exp].append((username, userid, prjname, prjid, counter))
                        user_set.add(userid)
                        prj_set.add(prjid)
                    counter += 1

                for email_item in EMail.objects.filter(registration__userid__in=user_set):
                    mail_table[email_item.registration.userid] = [ email_item.email ]
                for p_item in prj_set:
                    pmail_table[p_item] = get_prjadmin_emails(p_item)

            for days_to_exp, noti_list in noti_table.items():
                for username, userid, prjname, prjid, noti_idx in noti_list:
                    try:

                        servers, volumes = self.get_user_resources(userid, prjid)
                        res_pending = (len(servers) + len(volumes)) > 0
                        noti_params = {
                            'username' : username,
                            'project' : prjname,
                            'days' : days_to_exp,
                            'instances' : [ "%s (%s)" % (x.name, x.id) for x in servers ],
                            'volumes' : [ "%s (%s)" % (x.name, x.id) for x in volumes ],
                            'resources' : res_pending
                        }

                        rcpt_table = { 'to' : mail_table[userid] }
                        if noti_idx == 0 and res_pending:
                            rcpt_table['cc'] = pmail_table[prjid]

                        notifyUser(rcpt_table, USER_EXP_TYPE, noti_params,
                                   user_id=userid, project_id=prjid, dst_user_id=userid)
                    except:
                        LOG.error("Cannot notify %s" % username, exc_info=True)
                
        except:
            LOG.error("Notification failed", exc_info=True)
            raise CommandError("Notification failed")


