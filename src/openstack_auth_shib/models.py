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
from django.utils import timezone

# Used bit mask for project status
PRJ_PRIVATE = 0
PRJ_PUBLIC = 1
PRJ_GUEST = 3

#
# Project request must be handled by cloud admin first
#
PSTATUS_REG = 0
#
# Project request must be handled by project admin
#
PSTATUS_PENDING = 1
#
# Subscription renewal to be handled by cloud admin first
#
PSTATUS_RENEW_ADMIN = 10
#
# Subscription renewal to be handled by project admin
#
PSTATUS_RENEW_MEMB = 11


#
# Dummy value for RegRequest.flowstatus
#
RSTATUS_PENDING = 0

OS_ID_LEN = 64
OS_LNAME_LEN = 255
OS_SNAME_LEN = 64
EXT_ACCT_LEN = OS_LNAME_LEN
EMAIL_LEN = 255
PWD_LEN = 64

# Persistent data
class Registration(models.Model):
    regid = models.AutoField(primary_key=True)
    #
    # user id as registered in keystone
    # it's null if and only if the user is not yet
    # registered in keystone
    #
    userid = models.CharField(
        max_length=OS_ID_LEN,
        db_index=True,
        null=True
    )
    #
    # user name as registered in keystone
    #
    username = models.CharField(
        max_length=OS_LNAME_LEN,
        unique=True
    )
    givenname = models.CharField(max_length=OS_LNAME_LEN)
    sn = models.CharField(max_length=OS_LNAME_LEN)
    organization = models.CharField(max_length=OS_LNAME_LEN)
    phone = models.CharField(max_length=OS_SNAME_LEN)
    domain = models.CharField(max_length=OS_SNAME_LEN)
    #
    # deprecated
    # but it can be used as max expiration date
    #
    expdate = models.DateTimeField(
        db_index=True,
        null=True
    )

class Project(models.Model):
    #
    # project name as registered in keystone
    #
    projectname = models.CharField(
        max_length=OS_SNAME_LEN,
        primary_key=True
    )
    #
    # project id as registered in keystone
    # it's null if and only if the project is not yet
    # registered in keystone
    #
    projectid = models.CharField(
        max_length=OS_ID_LEN,
        null=True
    )
    description = models.TextField()
    #
    # Type of project (public, private, guest)
    #
    status = models.IntegerField()

class UserMapping(models.Model):
    #
    # the id provided by the SSO authority
    # for example the eduPersonPrincipalName
    #
    globaluser = models.CharField(
        max_length=EXT_ACCT_LEN,
        primary_key=True
    )
    registration = models.ForeignKey(Registration,
                                    db_index=False,
                                    on_delete=models.CASCADE)

class Expiration(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    expdate = models.DateTimeField(db_index=True)

class EMail(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    email = models.EmailField(max_length=EMAIL_LEN)

class PrjRole(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    roleid = models.CharField(max_length=OS_ID_LEN, null=False)
    status = models.IntegerField(default=0)

#Temporary data
class RegRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    password = models.CharField(max_length=PWD_LEN, null=True)
    externalid = models.CharField(max_length=EXT_ACCT_LEN, null=True)
    email = models.EmailField(max_length=EMAIL_LEN)
    #
    # not used, kept for back compatibility or for future features
    #
    flowstatus = models.IntegerField(default=RSTATUS_PENDING)
    contactper = models.CharField(max_length=OS_LNAME_LEN, null=True)
    notes = models.TextField()

#Temporary data
class PrjRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    #
    # Process status of the request, see PSTATUS_* for possible values
    #
    flowstatus = models.IntegerField(default=PSTATUS_REG)
    notes = models.TextField()


class NotificationLogManager(models.Manager):
    use_in_migrations = True

    def log_action(self, action, message,
                   project_id=None, user_id=None,
                   dst_project_id=None, dst_user_id=None):

        return self.model.objects.create(
            action=action,
            message=message,
            project_id=project_id,
            user_id=user_id,
            dst_project_id=dst_project_id,
            dst_user_id=dst_user_id,
        )


class NotificationLog(models.Model):
    objects = NotificationLogManager()

    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        editable=False,
        blank=False,
    )

    action = models.CharField(
        max_length=255,
        db_index=True,
        blank=False,
    )

    project_id = models.CharField(
        max_length=OS_ID_LEN,
        db_index=True,
        null=True,
        blank=True,
    )

    user_id = models.CharField(
        max_length=OS_ID_LEN,
        db_index=True,
        null=True,
        blank=True,
    )

    dst_project_id = models.CharField(
        max_length=OS_ID_LEN,
        db_index=True,
        null=True,
        blank=True,
    )

    dst_user_id = models.CharField(
        max_length=OS_ID_LEN,
        db_index=True,
        null=True,
        blank=True,
    )

    message = models.TextField(
        blank=False,
    )
