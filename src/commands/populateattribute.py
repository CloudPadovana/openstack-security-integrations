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

from django.db import transaction
from django.db.models import Max
from django.core.management.base import CommandError
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PrjAttribute
from openstack_auth_shib.utils import ATT_PRJ_EXP
from openstack_auth_shib.utils import ATT_PRJ_CIDR
from openstack_auth_shib.utils import ATT_PRJ_ORG

from horizon.management.commands.cronscript_utils import CloudVenetoCommand

from keystoneclient.v3 import client

LOG = logging.getLogger("populateattribute")

class Command(CloudVenetoCommand):

    def handle(self, *args, **options):

        super(Command, self).handle(options)

        try:
            LOG.info("Populating the attribute table")

            with transaction.atomic():
                for project in Project.objects.filter(projectid__isnull = False):
                    cnt = 0
                    admins = [ x.registration for x in PrjRole.objects.filter(project = project) ]
                    p_exp = Expiration.objects.filter(registration__in = admins).aggregate(Max('expdate'))
                    if PrjAttribute.objects.filter(project = project, name = ATT_PRJ_EXP).count() == 0:
                        PrjAttribute(project = project, name = ATT_PRJ_EXP,
                                     value = p_exp['expdate__max'].isoformat()).save()
                        cnt += 1
                    LOG.info("Update %d expiration date for %s" % (cnt, project.projectname))

        except:
            LOG.error("Import failed", exc_info=True)
            raise CommandError("Import failed")

