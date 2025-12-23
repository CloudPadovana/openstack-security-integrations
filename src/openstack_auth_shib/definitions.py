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

import re

from datetime import datetime
from datetime import timezone
from datetime import timedelta

from django.conf import settings

TENANTADMIN_ROLE = getattr(settings, 'OPENSTACK_KEYSTONE_TENANTADMIN_ROLE', 'project_manager')
TENANTADMIN_ROLEID = getattr(settings, 'OPENSTACK_KEYSTONE_TENANTADMIN_ROLE_ID', None)

DEFAULT_ROLE = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', 'member')
DEFAULT_ROLEID = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE_ID', None)

PRJ_REGEX = re.compile(r'[^a-zA-Z0-9-_ \.]')
REQID_REGEX = re.compile(r'^([0-9]+):([a-zA-Z0-9-_ \.]*)$')

ORG_TAG_FMT = "O=%s"
OU_TAG_FMT = "OU=%s"
TAG_REGEX = re.compile(r'([a-zA-Z0-9-_]+)=([^\s,/]+)$')


###############################################################################
# Definitions and utilities for courses
###############################################################################
ATT_COURSE_NAME = 1001
ATT_COURSE_DESC = 1002
ATT_COURSE_NOTE = 1003

COURSE_ATT_MAP = {
    ATT_COURSE_NAME : 'name',
    ATT_COURSE_DESC : 'description',
    ATT_COURSE_NOTE : 'notes',
}

###############################################################################
# Definitions and utilities for expiration date
###############################################################################
try:
    YEARS_RANGE = int(getattr(settings, 'YEARS_RANGE', '10'))
except:
    YEARS_RANGE = 10

def get_year_list(n_of_years = YEARS_RANGE):
    curr_year = datetime.now(timezone.utc).year
    return list(range(curr_year, curr_year + n_of_years))

def NOW():
    return datetime.now(timezone.utc)

def FROMNOW(days):
    return datetime.now(timezone.utc) + timedelta(days)

try:
    MAX_RENEW = int(getattr(settings, 'TENANT_MAX_RENEW', '4'))
except:
    MAX_RENEW = 4

ATT_PRJ_EXP = 2001

###############################################################################
# Misc
###############################################################################

ATT_PRJ_CPER = 2002

ATT_PRJ_CIDR = 2011
ATT_PRJ_ORG = 2012
ATT_PRJ_OU = 2013

CIDR_PATTERN = re.compile(r'([0-9]+\.[0-9]+)\.([0-9]+)\.0/[0-9]+')
MAX_AVAIL = getattr(settings, 'MAX_PROPOSED_NETWORKS', 10)

ID_REGEX_TABLE = {
    'infn.it' : re.compile(r'^[a-f0-9]+-[a-f0-9]+-[a-f0-9]+-[a-f0-9]+-[a-f0-9]+@infn\.it')
}
def isRawID(uid):
    for label, u_regex in ID_REGEX_TABLE.items():
        if u_regex.search(uid) != None:
            return True
    return False


