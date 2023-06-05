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
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import RSTATUS_DISABLING
from openstack_auth_shib.models import RSTATUS_DISABLED
from openstack_auth_shib.models import RSTATUS_REENABLING
from openstack_auth_shib.models import PSTATUS_RENEW_DISC

from horizon.management.commands.cronscript_utils import CloudVenetoCommand

LOG = logging.getLogger("checkgateaccess")

class Command(CloudVenetoCommand):

    def schedule_ban(self):
        try:
            with transaction.atomic():

                qset1 = RegRequest.objects.all()
                pend_orphans = set(qset1.values_list('registration', flat = True).distinct())

                qset2 = Expiration.objects.all()
                act_users = set(qset2.values_list('registration', flat = True).distinct())

                qset3 = PrjRequest.objects.exclude(flowstatus = PSTATUS_RENEW_DISC)
                pend_prjusr = set(qset3.values_list('registration', flat = True).distinct())

                new_orphans = Registration.objects.exclude(regid__in = pend_orphans | act_users | pend_prjusr)
                for item in new_orphans:
                    q_args = {
                        'registration' : item,
                        'email' : "-",
                        'flowstatus' : RSTATUS_DISABLING,
                        'notes' : "-"
                    }
                    RegRequest(**q_args).save()
                    LOG.info("Scheduled ban for %s" % item.username)
        except:
            LOG.error("Orphan schedule failed", exc_info=True)
            raise CommandError("Orphan schedule failed")

    def run_remote_script(self, remote_script, u_email):
        try:
            cmd_args = [
                '/usr/bin/ssh', '-i', self.config.key_path,
                '-oStrictHostKeyChecking=no',
                '-oUserKnownHostsFile=/tmp/horizon_known_hosts',
                "%s@%s" % (self.config.gate_user, self.config.gate_address),
                remote_script, u_email
            ]
            ssh_proc = subprocess.run(cmd_args)
        except:
            LOG.error("Cannot disable user %s on gate" % orphan.registration.username, exc_info=True)
            return False

        return ssh_proc.returncode == 0

    def ban_user(self):
        disabled_users = list()
        with transaction.atomic():
            qset3 = RegRequest.objects.filter(flowstatus = RSTATUS_DISABLING)
            for orphan in EMail.objects.filter(registration__in = [ x.registration for x in qset3 ]):
                if self.run_remote_script(self.config.ban_script, orphan.email):
                    disabled_users.append(orphan.registration)

            qset4 = RegRequest.objects.filter(registration__in = disabled_users)
            qset4.update(flowstatus = RSTATUS_DISABLED)

        for orphan in disabled_users:
            LOG.info("Disabled user %s" % orphan.username)

    def allow_user(self):
        enabled_users = list()
        with transaction.atomic():
            qset5 = RegRequest.objects.filter(flowstatus = RSTATUS_REENABLING)
            for orphan in EMail.objects.filter(registration__in = [ x.registration for x in qset5 ]):
                if self.run_remote_script(self.config.allow_script, orphan.email):
                    enabled_users.append(orphan.registration)

            RegRequest.objects.filter(registration__in = enabled_users).delete()

        for orphan in enabled_users:
            LOG.info("Enabled user %s" % orphan.username)

    def handle(self, *args, **options):
    
        super(Command, self).handle(options)
        if not self.config.key_path or not self.config.gate_address:
            return

        self.schedule_ban()

        if self.config.ban_script:
            time.sleep(1)
            self.ban_user()

        if self.config.allow_script:
            time.sleep(1)
            self.allow_user()

