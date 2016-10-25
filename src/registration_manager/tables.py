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

from openstack_auth_shib.models import Registration, RegRequest

from horizon import tables

LOG = logging.getLogger(__name__)

class ProcessLink(tables.LinkAction):
    name = "reqprocess"
    verbose_name = _("Process")
    url = "horizon:idmanager:registration_manager:process"
    classes = ("ajax-modal", "btn-edit")

class RegisterTable(tables.DataTable):
    regid = tables.Column('regid', verbose_name=_('ID'))
    username = tables.Column('username', verbose_name=_('User name'))
    givenname = tables.Column('givenname', verbose_name=_('First name'))
    sn = tables.Column('sn', verbose_name=_('Last name'))
    organization = tables.Column('organization', verbose_name=_('Organization'))
    phone = tables.Column('phone', verbose_name=_('Phone number'))

    class Meta:
        name = "register_table"
        verbose_name = _("Registrations")
        row_actions = (ProcessLink, )

    def get_object_id(self, datum):
        return datum.regid


###############################################################################
#
#  New implementation
#
###############################################################################
class RegistrData:

    NEW_USR_NEW_PRJ = 1
    NEW_USR_EX_PRJ = 2
    EX_USR_NEW_PRJ = 3
    EX_USR_EX_PRJ = 4

    def __init__(self):
        self.requestid = None
        self.username = None
        self.fullname = None
        self.organization = None
        self.phone = None
        self.project = "-"
        self.code = 0
    
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
    url = "horizon:idmanager:registration_manager:precheck"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.NEW_USR_NEW_PRJ

class RejectLink(tables.LinkAction):
    name = "rejectlink"
    verbose_name = _("Reject")
    url = "horizon:idmanager:registration_manager:reject"
    classes = ("ajax-modal", "btn-edit")
    
    def allowed(self, request, datum):
        return datum.code == RegistrData.NEW_USR_EX_PRJ or datum.code == RegistrData.NEW_USR_NEW_PRJ

class NewPrjLink(tables.LinkAction):
    #
    # TODO implement
    #
    name = "newprjlink"
    verbose_name = _("Create Project")
    url = "horizon:idmanager:registration_manager:precheck"
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

def get_description(data):
    if data.code == RegistrData.NEW_USR_NEW_PRJ:
        return _('New user and new project')
    elif data.code == RegistrData.NEW_USR_EX_PRJ:
        return _('New user to be pre-checked')
    elif data.code == RegistrData.EX_USR_NEW_PRJ:
        return _('User requires a new project')
    else:
        return _('User requires membership')

class OperationTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    organization = tables.Column('organization', verbose_name=_('Organization'))
    phone = tables.Column('phone', verbose_name=_('Phone number'))
    project = tables.Column('project', verbose_name=_('Project'))
    description = tables.Column(get_description, verbose_name=_('Description'))

    class Meta:
        name = "operation_table"
        verbose_name = _("Pending requests")
        row_actions = (PreCheckLink,
                       GrantAllLink,
                       RejectLink,
                       NewPrjLink,
                       ForceApprLink,
                       ForceRejLink)

    def get_object_id(self, datum):
        return datum.requestid

