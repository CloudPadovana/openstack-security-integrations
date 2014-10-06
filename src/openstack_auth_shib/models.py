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

from django.db import models

# Used bit mask for project status
PRJ_PRIVATE = 0
PRJ_PUBLIC = 1
PRJ_GUEST = 3

# Status for project approval
PSTATUS_REG = 0
PSTATUS_PENDING = 1
PSTATUS_APPR = 2
PSTATUS_REJ = 3

# Status for registration approval
RSTATUS_PENDING = 0
RSTATUS_PRECHKD = 1
RSTATUS_CHECKED = 2
RSTATUS_NOFLOW = 3
#
#   PENDING -----------------------+
#   (requests for registration)    |
#                                  +--- CHECKED -- (approved)
#                                  |
#   PRECHKD -----------------------+
#   (requests for prj membership) 


OS_ID_LEN = 64
OS_LNAME_LEN = 255
OS_SNAME_LEN = 64
EXT_ACCT_LEN = OS_LNAME_LEN
EMAIL_LEN = 255
PWD_LEN = 64

# Persistent data
class Registration(models.Model):
    regid = models.AutoField(primary_key=True)
    userid = models.CharField(
        max_length=OS_ID_LEN,
        db_index=True,
        null=True
    )                                   #local user id
    username = models.CharField(
        max_length=OS_LNAME_LEN,
        unique=True
    )                                   #local user name
    givenname = models.CharField(max_length=OS_LNAME_LEN)
    sn = models.CharField(max_length=OS_LNAME_LEN)
    organization = models.CharField(max_length=OS_LNAME_LEN)
    phone = models.CharField(max_length=OS_SNAME_LEN)
    domain = models.CharField(max_length=OS_SNAME_LEN)
    expdate = models.DateTimeField(
        db_index=True,
        null=True
    )

class Project(models.Model):
    projectname = models.CharField(
        max_length=OS_SNAME_LEN,
        primary_key=True
    )
    projectid = models.CharField(
        max_length=OS_ID_LEN,
        null=True
    )
    description = models.TextField()
    status = models.IntegerField()

class UserMapping(models.Model):
    globaluser = models.CharField(
        max_length=EXT_ACCT_LEN,
        primary_key=True
    )
    registration = models.ForeignKey(Registration,
                                    db_index=False,
                                    on_delete=models.CASCADE)


#Temporary data
class RegRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    password = models.CharField(max_length=PWD_LEN, null=True)
    externalid = models.CharField(max_length=EXT_ACCT_LEN, null=True)
    email = models.EmailField(max_length=EMAIL_LEN)
    flowstatus = models.IntegerField(default=RSTATUS_PENDING)
    contactper = models.CharField(max_length=OS_LNAME_LEN, null=True)
    notes = models.TextField()

class PrjRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    flowstatus = models.IntegerField(default=PSTATUS_REG)
    notes = models.TextField()


