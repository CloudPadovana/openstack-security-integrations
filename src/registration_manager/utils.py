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

from django.conf import settings
from django.utils.translation import ugettext as _

from openstack_dashboard.api import keystone as keystone_api
from openstack_dashboard.api import neutron as neutron_api

LOG = logging.getLogger(__name__)

class RegistrData:

    NEW_USR_NEW_PRJ = 1
    NEW_USR_EX_PRJ = 2
    EX_USR_NEW_PRJ = 3
    EX_USR_EX_PRJ = 4
    USR_RENEW = 5
    PRJADM_RENEW = 6
    REMINDER = 7
    ORPHAN = 8

    DESCRARRAY = [
        _('Unknown operation'),
        _('New user and new project'),
        _('New user to be pre-checked'),
        _('User requires a new project'),
        _('User requires membership'),
        _('User requires renewal before '),
        _('Project administrator requires renewal before'),
        _('User requires post registration actions'),
        _('Registered user is orphan')
    ]

    def __init__(self, **kwargs):

        self.requestid = kwargs.get('requestid',None)
        self.code = int(kwargs.get('code', '0'))
        self.project = "-"
        self.notes = None
        if 'registration' in kwargs:
            registration = kwargs['registration']
            self.username = registration.username
            self.fullname = registration.givenname + " " + registration.sn
            self.organization = registration.organization
            self.phone = registration.phone
        else:
            self.username = None
            self.fullname = None
            self.organization = None
            self.phone = None

    def __lt__(self, other):
        return self.username < other.username or (self.username == other.username and self.project < other.project)

    def __gt__(self, other):
        return self.username > other.username or (self.username == other.username and self.project > other.project)

    def __eq__(self, other):
        return self.username == other.username and self.project == other.project

    def __ne__(self, other):
        return not self.__eq__(other)

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)

    def __repr__(self):
        if self.code >= len(RegistrData.DESCRARRAY):
            self.code = 0

        result = RegistrData.DESCRARRAY[self.code]
        if self.notes:
            result += " %s" % str(self.notes)    
        return result  


def getProjectInfo(request, project):
    result = { 'name' : project.projectname, 'comp_required' : False }

    comp_rules = getattr(settings, 'COMPLIANCE_RULES', None)
    if not comp_rules:
        return result

    try:
        kprj_man = keystone_api.keystoneclient(request).projects
        for item in comp_rules['organizations']:
            if ('O=' + item) in kprj_man.list_tags(project.projectid):
                result['comp_required'] = True
    except:
        LOG.error("Registration error", exc_info=True)
        result['err_msg'] = _("Cannot retrieve organization tag")

    try:
        for s_item in neutron_api.subnet_list(request, project_id = project.projectid):
            for p_item in comp_rules['subnets']:
                if p_item in item.cidr:
                    result['comp_required'] = True
    except:
        LOG.error("Registration error", exc_info=True)
        result['err_msg'] = _("Cannot retrieve subnetwork")

    return result


