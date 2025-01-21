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
from django.urls import reverse
from django.utils.translation import gettext as _

from horizon import tables

from .utils import RegistrData

LOG = logging.getLogger(__name__)

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

class DetailsLink(tables.LinkAction):
    name = "detailslink"
    verbose_name = _("Details")
    url = "horizon:idmanager:registration_manager:details"
    classes = ("ajax-modal", "btn-edit")

class ReminderAck(tables.LinkAction):
    name = "reminder_ack"
    verbose_name = _("Done")
    url = "horizon:idmanager:registration_manager:remainderack"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.REMINDER or datum.code == RegistrData.ORPHAN

class ChkCompAck(tables.LinkAction):
    name = "chkcomp_ack"
    verbose_name = _("Compliance ok")
    url = "horizon:idmanager:registration_manager:compack"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.CHK_COMP

class PromoteAdminLink(tables.LinkAction):
    name = "promoteadminlink"
    verbose_name = _("Promote Admin")
    url = "horizon:idmanager:registration_manager:promoteadmin"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.PRO_ADMIN

class OperationTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    organization = tables.Column('organization', verbose_name=_('Home institution'))
    project = tables.Column('project', verbose_name=_('Project'))
    description = tables.Column(repr, verbose_name=_('Description'))

    class Meta:
        name = "operation_table"
        verbose_name = _("Pending requests")
        row_actions = (PreCheckLink,
                       ChkCompAck,
                       PromoteAdminLink,
                       GrantAllLink,
                       RejectLink,
                       NewPrjLink,
                       RejectPrjLink,
                       ForceApprLink,
                       ForceRejLink,
                       RenewAdminLink,
                       ForcedRenewLink,
                       ReminderAck,
                       DetailsLink)

    def get_object_id(self, datum):
        return datum.requestid

