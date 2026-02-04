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

from django.db import transaction
from django.core.management.base import CommandError

from openstack_auth_shib.models import Log

from horizon.management.commands.cronscript_utils import CloudVenetoCommand

LOG = logging.getLogger("deleteusersfromlog")

class Command(CloudVenetoCommand):

    def handle(self, *args, **options):
    
        super(Command, self).handle(options)

        try:
            with transaction.atomic():

                t_offset = int(self.config.get('LOGCLEANUP_OFFSET', 365));
                tstamp = datetime.now(timezone.utc) - timedelta(days = t_offset)

                p_users = Log.objects.filter(action = 'user_purged', timestamp__lt = tstamp)
                for uitem in p_users.values_list('dst_user_id', flat = True):
                    Log.objects.filter(user_id = uitem).delete()
                    Log.objects.filter(dst_user_id = uitem).delete()
                LOG.info("Removed %s from log" % uitem)
        except:
            LOG.error("Users cleanup failed", exc_info=True)
