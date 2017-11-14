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

from optparse import make_option

from django.db import transaction
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import SUBSCR_REMINDER

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app

LOG = logging.getLogger("pendingsubscr")

class Command(BaseCommand):

    option_list = build_option_list()

    def handle(self, *args, **options):

        configure_log(options)

        config = configure_app(options)

        admin_table = dict()
        mail_table = dict()
        req_table = dict()

        try:
            with transaction.atomic():

                for prj_req in PrjRequest.objects.filter(flowstatus=PSTATUS_PENDING):
                    prjname = prj_req.project.projectname
                    if not req_table.has_key(prjname):
                        req_table[prjname] = list()
                    req_table[prjname].append(prj_req.registration.username)

                for prjname in req_table.keys():
                    for p_role in PrjRole.objects.filter(project__projectname=prjname):

                        user_name = p_role.registration.username
                        user_id = p_role.registration.userid
                        user_tuple = (user_name, user_id)

                        if not admin_table.has_key(user_tuple):
                            admin_table[user_tuple] = list()
                        admin_table[user_tuple].append(p_role.project.projectname)

                        if not mail_table.has_key(user_name):
                            tmpres = EMail.objects.filter(registration__username=user_name)
                            if len(tmpres):
                                mail_table[user_name] = tmpres[0].email

            for user_tuple in admin_table:
                for prj_name in admin_table[user_tuple]:
                    try:
                        noti_params = {
                            'pendingreqs' : req_table[prj_name],
                            'project' : prj_name
                        }
                        notifyUser(mail_table[user_tuple[0]], SUBSCR_REMINDER, noti_params,
                                   dst_user_id=user_tuple[1])
                    except:
                        LOG.error("Cannot notify pending subscription: %s" % user_tuple[0], 
                                  exc_info=True)

        except:
            LOG.error("Cannot notify pending subscritions: system error", exc_info=True)
            raise CommandError("Cannot notify pending subscritions")


