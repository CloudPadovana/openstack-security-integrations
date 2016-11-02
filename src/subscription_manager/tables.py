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

from django.utils.translation import ugettext_lazy as _

from horizon import tables

LOG = logging.getLogger(__name__)

class ApproveLink(tables.LinkAction):
    name = "apprsubscr"
    verbose_name = _("Approve")
    url = "horizon:idmanager:subscription_manager:approve"
    classes = ("ajax-modal", "btn-edit")

class RejectLink(tables.LinkAction):
    name = "rejsubscr"
    verbose_name = _("Reject")
    url = "horizon:idmanager:subscription_manager:reject"
    classes = ("ajax-modal", "btn-edit")

class SubscriptionTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    notes = tables.Column('notes', verbose_name=_('Notes'))
    expiration = tables.Column('expiration', verbose_name=_('Expiration date'))

    class Meta:
        name = "subscription_table"
        verbose_name = _("Subscriptions")
        row_actions = (ApproveLink, RejectLink)
        table_actions = ()

    def get_object_id(self, datum):
        return datum.regid





