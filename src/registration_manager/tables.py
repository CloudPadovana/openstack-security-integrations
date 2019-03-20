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

from django import shortcuts
from django.db import transaction
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

from horizon import tables

from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import RSTATUS_REMINDER

LOG = logging.getLogger(__name__)

class RegistrData:

    NEW_USR_NEW_PRJ = 1
    NEW_USR_EX_PRJ = 2
    EX_USR_NEW_PRJ = 3
    EX_USR_EX_PRJ = 4
    NEW_USR_GUEST_PRJ = 5
    USR_RENEW = 6
    PRJADM_RENEW = 7
    GUEST_RENEW = 8
    REMINDER = 9
    ORPHAN = 10

    DESCRARRAY = [
        _('Unknown operation'),
        _('New user and new project'),
        _('New user to be pre-checked'),
        _('User requires a new project'),
        _('User requires membership'),
        _('New user requires access as guest'),
        _('User requires renewal before '),
        _('Project administrator requires renewal before'),
        _('Guest requires renewal before'),
        _('User requires post registration actions'),
        _('Registered user is orphan')
    ]

    def __init__(self):
        self.requestid = None
        self.username = None
        self.fullname = None
        self.organization = None
        self.phone = None
        self.project = "-"
        self.code = 0
        self.notes = None
    
    def __cmp__(self, other):
        if self.username < other.username:
            return -1
        if self.username > other.username:
            return 1
        if self.project < other.project:
            return -1
        if self.project > other.project:
            return 1
        return 0

    def __repr__(self):
        if self.code >= len(RegistrData.DESCRARRAY):
            self.code = 0

        result = RegistrData.DESCRARRAY[self.code]
        if self.notes:
            result += " %s" % str(self.notes)    
        return result  

class PreCheckLink(tables.LinkAction):
    name = "prechklink"
    verbose_name = _("Pre Check")
    url = "horizon:idmanager:registration_manager:precheck"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.NEW_USR_EX_PRJ

class GrantAllLink(tables.LinkAction):
    name = "grantalllink"
    verbose_name = _("Authorize All")
    url = "horizon:idmanager:registration_manager:grantall"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.NEW_USR_NEW_PRJ

class RejectLink(tables.LinkAction):
    name = "rejectlink"
    verbose_name = _("Reject")
    url = "horizon:idmanager:registration_manager:reject"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        result = datum.code == RegistrData.NEW_USR_EX_PRJ
        result = result or datum.code == RegistrData.NEW_USR_NEW_PRJ
        return result

class NewPrjLink(tables.LinkAction):
    name = "newprjlink"
    verbose_name = _("Create Project")
    url = "horizon:idmanager:registration_manager:newproject"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.EX_USR_NEW_PRJ

class RejectPrjLink(tables.LinkAction):
    name = "rejectprjlink"
    verbose_name = _("Reject")
    url = "horizon:idmanager:registration_manager:rejectproject"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.EX_USR_NEW_PRJ

class ForceApprLink(tables.LinkAction):
    name = "forceapprlink"
    verbose_name = _("Forced Approve")
    url = "horizon:idmanager:registration_manager:forcedapprove"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.EX_USR_EX_PRJ

class ForceRejLink(tables.LinkAction):
    name = "forcerejlink"
    verbose_name = _("Forced Reject")
    url = "horizon:idmanager:registration_manager:forcedreject"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.EX_USR_EX_PRJ

class GuestApprLink(tables.LinkAction):
    name = "guestapprlink"
    verbose_name = _("Guest Approve")
    url = "horizon:idmanager:registration_manager:guestapprove"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.NEW_USR_GUEST_PRJ

class GuestRejLink(tables.LinkAction):
    name = "guestrejlink"
    verbose_name = _("Guest Reject")
    url = "horizon:idmanager:registration_manager:reject"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.NEW_USR_GUEST_PRJ

class RenewAdminLink(tables.LinkAction):
    name = "renewadminlink"
    verbose_name = _("Renew admin")
    url = "horizon:idmanager:registration_manager:renewadmin"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.PRJADM_RENEW

class ForcedRenewLink(tables.LinkAction):
    name = "forcedrenewlink"
    verbose_name = _("Forced renew")
    url = "horizon:idmanager:registration_manager:forcedrenew"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.USR_RENEW

class GuestRenewLink(tables.LinkAction):
    name = "guestrenewlink"
    verbose_name = _("Guest renew")
    url = "horizon:idmanager:registration_manager:forcedrenew"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.GUEST_RENEW

class DetailsLink(tables.LinkAction):
    name = "detailslink"
    verbose_name = _("Details")
    url = "horizon:idmanager:registration_manager:details"
    classes = ("ajax-modal", "btn-edit")

class ReminderAck(tables.Action):
    name = "reminder_ack"
    verbose_name = _("Done")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.REMINDER or datum.code == RegistrData.ORPHAN

    def single(self, data_table, request, object_id):

        with transaction.atomic():
            req_data = object_id.split(':')
            RegRequest.objects.filter(
                registration__regid = int(req_data[0]),
                flowstatus = RSTATUS_REMINDER
            ).delete()

        return shortcuts.redirect(reverse('horizon:idmanager:registration_manager:index'))

class OperationTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    organization = tables.Column('organization', verbose_name=_('Organization'))
    phone = tables.Column('phone', verbose_name=_('Phone number'))
    project = tables.Column('project', verbose_name=_('Project'))
    description = tables.Column(repr, verbose_name=_('Description'))

    class Meta:
        name = "operation_table"
        verbose_name = _("Pending requests")
        row_actions = (PreCheckLink,
                       GrantAllLink,
                       RejectLink,
                       NewPrjLink,
                       RejectPrjLink,
                       ForceApprLink,
                       ForceRejLink,
                       GuestApprLink,
                       GuestRejLink,
                       RenewAdminLink,
                       GuestRenewLink,
                       ForcedRenewLink,
                       ReminderAck,
                       DetailsLink)

    def get_object_id(self, datum):
        return datum.requestid

