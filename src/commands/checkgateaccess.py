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
import subprocess
import time

from django.db import transaction
from django.core.management.base import CommandError

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import RSTATUS_DISABLING
from openstack_auth_shib.models import RSTATUS_DISABLED
from openstack_auth_shib.models import RSTATUS_REMINDER
from openstack_auth_shib.models import RSTATUS_REMINDACK

from horizon.management.commands.cronscript_utils import CloudVenetoCommand

LOG = logging.getLogger("checkgateaccess")

class Command(CloudVenetoCommand):

    def schedule_ban(self):
        try:
            with transaction.atomic():

                safe_states = [
                    RSTATUS_DISABLING,
                    RSTATUS_DISABLED,
                    RSTATUS_REMINDER,
                    RSTATUS_REMINDACK
                ]
                qset1 = RegRequest.objects.filter(flowstatus__in = safe_states)
                pend_orphans = set(qset1.values_list('registration', flat = True).distinct())

                qset2 = Expiration.objects.all()
                act_users = set(qset2.values_list('registration', flat = True).distinct())

                new_orphans = Registration.objects.exclude(regid__in = pend_orphans | act_users)
                for item in new_orphans:
                    q_args = {
                        'registration' : item,
                        'email' : "-",
                        'flowstatus' : RSTATUS_DISABLING,
                        'notes' : "-"
                    }
                    RegRequest(**q_args).save()
        except:
            LOG.error("Orphan schedule failed", exc_info=True)
            raise CommandError("Orphan schedule failed")


    def ban_user(self):
        disabled_users = list()
        qset3 = RegRequest.objects.filter(flowstatus = RSTATUS_DISABLING)
        for orphan in EMail.objects.filter(registration__in = [ x.registration for x in qset3 ]):
            try:
                cmd_args = [
                    '/usr/bin/ssh', '-i', self.config.key_path,
                    '-oStrictHostKeyChecking=no',
                    '-oUserKnownHostsFile=/tmp/horizon_known_hosts',
                    "%s@%s" % (self.config.gate_user, self.config.gate_address),
                    self.config.ban_script, orphan.email
                ]
                ssh_proc = subprocess.run(cmd_args)
                if ssh_proc.returncode == 0:
                    disabled_users.append(orphan.registration)
            except:
                LOG.error("Cannot disable user %s on gate" % orphan.registration.username, exc_info=True)

        RegRequest.objects.filter(registration__in = disabled_users).update(flowstatus = RSTATUS_DISABLED)
        for orphan in disabled_users:
            LOG.info("Disabled user %s" % orphan.username)


    def handle(self, *args, **options):
    
        super(Command, self).handle(options)
        if not self.config.key_path or not self.config.gate_address or not self.config.ban_script:
            return

        self.schedule_ban()

        time.sleep(1)

        self.ban_user()

