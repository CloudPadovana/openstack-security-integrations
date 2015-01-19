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

from horizon import tables

LOG = logging.getLogger(__name__)

class DeleteMemberAction(tables.DeleteAction):
    data_type_singular = _("Member")
    data_type_plural = _("Members")

    def delete(self, request, obj_id):
        pass

class MemberTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    userid = tables.Column('userid', verbose_name=_('User ID'))
    givenname = tables.Column('givenname', verbose_name=_('First name'))
    sn = tables.Column('sn', verbose_name=_('Last name'))
    organization = tables.Column('organization', verbose_name=_('Organization'))
    role = tables.Column('role', verbose_name=_('Role'))
    
    class Meta:
        name = "member_table"
        verbose_name = _("Project members")
        row_actions = (DeleteMemberAction,)
        table_actions = (DeleteMemberAction,)

    def get_object_id(self, datum):
        return datum.userid





