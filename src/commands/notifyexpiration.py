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
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import USER_EXP_TYPE

from horizon.management.commands.cronscript_utils import build_option_list
from horizon.management.commands.cronscript_utils import configure_log
from horizon.management.commands.cronscript_utils import configure_app

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
            noti_table = dict()
            user_set = set()
            prj_set = set()

            for days_to_exp in self._get_days_to_exp(config.cron_plan):

                tframe = now + timedelta(days=days_to_exp)
                noti_table[days_to_exp] = list()

                q_args = {
                    'expdate__gte' : tframe.replace(hour=0, minute=0, second=0, microsecond=0),
                    'expdate__lte' : tframe.replace(hour=23, minute=59, second=59, microsecond=999999)
                }

                for exp_item in Expiration.objects.filter(**q_args):

                    username = exp_item.registration.username
                    userid = exp_item.registration.userid
                    prjname = exp_item.project.projectname
                    prjid = exp_item.project.projectid

                    noti_table[days_to_exp].append((username, userid, prjname, prjid))
                    user_set.add(userid)
                    prj_set.add(prjname)

            admin_table = dict()
            for p_role in PrjRole.objects.filter(project__projectname__in=prj_set):
                prjname = p_role.project.projectname
                if not admin_table.has_key(prjname):
                    admin_table[prjname] = list()
                admin_table[prjname].append(p_role.registration.userid)
                user_set.add(p_role.registration.userid)

            mail_table = dict()
            for email_item in EMail.objects.filter(registration__userid__in=user_set):
                mail_table[email_item.registration.userid] = email_item.email

            contact_table = dict()
            for prjname, uid_list in admin_table.items():
                contact_table[prjname] = list()
                for userid in uid_list:
                    if mail_table.has_key(userid):
                        contact_table[prjname].append(mail_table[userid])

            for days_to_exp, noti_list in noti_table.items():
                for username, userid, prjname, prjid in noti_list:
                    try:
                        noti_params = {
                            'username' : username,
                            'project' : prjname,
                            'days' : days_to_exp,
                            'contacts' : contact_table[prjname]
                        }
                        notifyUser(mail_table[userid], USER_EXP_TYPE, noti_params,
                                   user_id=userid, project_id=prjid, dst_user_id=userid)
                    except:
                        LOG.error("Cannot notify %s" % username, exc_info=True)
                
        except:
            LOG.error("Notification failed", exc_info=True)
            raise CommandError("Notification failed")


