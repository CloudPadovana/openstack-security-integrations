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

from datetime import datetime
from datetime import timezone as tzone

from django.db import models
from django.utils import timezone

NEW_MODEL = False

# Used bit mask for project status
PRJ_PRIVATE = 0
PRJ_PUBLIC = 1
PRJ_COURSE = 2

#
# Project request must be handled by cloud admin first
#
PSTATUS_REG = 0
#
# Project request must be handled by project admin
#
PSTATUS_PENDING = 1
#
# Project request must be checked for compliance
#
PSTATUS_CHK_COMP = 2
#
# Subscription renewal to be handled by cloud admin first
#
PSTATUS_RENEW_ADMIN = 10
#
# Subscription renewal to be handled by project admin
#
PSTATUS_RENEW_MEMB = 11
#
# Subscription renewal proposed to the user
#
PSTATUS_RENEW_ATTEMPT = 12
#
# Subscription renewal rejected to the user
#
PSTATUS_RENEW_DISC = 13

#
# Registration request is waiting for pre-check
#
RSTATUS_PENDING = 0
#
# Reminder for cloud admin (first step)
#
RSTATUS_REMINDER = 1
#
# Reminder for cloud admin (final step)
#
RSTATUS_REMINDACK = 2
#
# Orphan user scheduled for ban on gate
#
RSTATUS_DISABLING = 3
#
# Orphan user banned on gate
#
RSTATUS_DISABLED = 4
#
# Orphan user to be re-enabled on gate
#
RSTATUS_REENABLING = 5

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
    # Type of project (private, public, course)
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

class ExpManager(models.Manager):
    use_in_migrations = True

    def create_expiration(self, **kwargs):
        reg_item = kwargs['registration']
        result = self.model.objects.create(
            registration = reg_item,
            project = kwargs['project'],
            expdate = kwargs['expdate']
        )

        if reg_item.expdate < kwargs['expdate']:
            reg_item.expdate = kwargs['expdate']
            reg_item.save()

        return result

    def _operate_expiration(self, op, **kwargs):
        q_args = dict()
        if 'registration' in kwargs:
            q_args['registration'] = kwargs['registration']
        elif 'registration__regid' in kwargs:
            q_args['registration__regid'] = kwargs['registration__regid']
        elif 'registration__userid' in kwargs:
            q_args['registration__userid'] = kwargs['registration__userid']
        else:
            raise Exception('Missing registration')

        if 'project' in kwargs:
            q_args['project'] = kwargs['project']
        elif 'project__projectname' in kwargs:
            q_args['project__projectname'] = kwargs['project__projectname']
        elif 'project__projectid' in kwargs:
            q_args['project__projectid'] = kwargs['project__projectid']
        else:
            raise Exception('Missing project')

        prj_exp = self.model.objects.filter(**q_args)
        if len(prj_exp) == 0:
            return
        regid = prj_exp[0].registration.regid

        if op == 0:
            prj_exp.update(expdate = kwargs['expdate'])
        else:
            prj_exp.delete()

        all_exp = self.model.objects.filter(
            registration__regid = regid
        )
        if len(all_exp):
            new_exp = max([ x.expdate for x in all_exp ])
            all_exp[0].registration.expdate = new_exp
            all_exp[0].registration.save()
        else:
            newdate = datetime.now(tzone.utc)
            Registration.objects.filter(regid = regid).update(expdate = newdate)

    def update_expiration(self, **kwargs):
        self._operate_expiration(0, **kwargs)

    def delete_expiration(self, **kwargs):
        self._operate_expiration(1, **kwargs)


class Expiration(models.Model):
    objects = ExpManager()

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

if NEW_MODEL:
    class PrjAttribute(models.Model):
        project = models.ForeignKey(Project, on_delete=models.CASCADE)
        name = models.IntegerField(default=0)
        value = models.TextField()

#Temporary data
class RegRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    password = models.CharField(max_length=PWD_LEN, null=True)
    externalid = models.CharField(max_length=EXT_ACCT_LEN, null=True)
    email = models.EmailField(max_length=EMAIL_LEN)
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


class LogManager(models.Manager):
    use_in_migrations = True

    def log_action(self, log_type, action, message,
                   project_id=None, user_id=None,
                   project_name=None, user_name=None,
                   dst_project_id=None, dst_user_id=None,
                   extra={}):

        log = self.model.objects.create(
            log_type=log_type,
            action=action,
            message=message,
            project_id=project_id,
            user_id=user_id,
            project_name=project_name,
            user_name=user_name,
            dst_project_id=dst_project_id,
            dst_user_id=dst_user_id,
        )

        for k, v in extra.items():
            log.logextra_set.create(key=k, value=v)

        return log


class Log(models.Model):
    objects = LogManager()

    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        editable=False,
        blank=False,
    )

    log_type = models.CharField(
        max_length=255,
        db_index=True,
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

    project_name = models.CharField(
        max_length=OS_SNAME_LEN,
        db_index=True,
        null=True,
        blank=True,
    )

    user_name = models.CharField(
        max_length=OS_SNAME_LEN,
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


class LogExtra(models.Model):
    log = models.ForeignKey(Log, on_delete=models.PROTECT)

    key = models.CharField(
        max_length=255,
        db_index=True,
        blank=False,
    )

    value = models.TextField(
        blank=False,
    )
