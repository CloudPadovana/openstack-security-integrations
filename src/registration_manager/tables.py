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
from django.utils.translation import ugettext_lazy as _

from openstack_auth_shib.models import Registration, RegRequest

from horizon import tables

LOG = logging.getLogger(__name__)

class ProcessLink(tables.LinkAction):
    name = "reqprocess"
    verbose_name = _("Process")
    url = "horizon:identity:registration_manager:process"
    classes = ("ajax-modal", "btn-edit")

class RegisterTable(tables.DataTable):
    regid = tables.Column('regid', verbose_name=_('ID'))
    username = tables.Column('username', verbose_name=_('User name'))
    givenname = tables.Column('givenname', verbose_name=_('First name'))
    sn = tables.Column('sn', verbose_name=_('Last name'))
    organization = tables.Column('organization', verbose_name=_('Organization'))
    phone = tables.Column('phone', verbose_name=_('Phone number'))
    domain = tables.Column('domain', verbose_name=_('Domain'))

    class Meta:
        name = "register_table"
        verbose_name = _("Registrations")
        row_actions = (ProcessLink, )

    def get_object_id(self, datum):
        return datum.regid





