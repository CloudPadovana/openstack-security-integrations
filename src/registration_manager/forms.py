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

import sys
import re
import logging
import string
import secrets

from datetime import datetime

from horizon import forms
from horizon import messages

from django.db import transaction
from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.forms.widgets import SelectDateWidget
from django.views.decorators.debug import sensitive_variables
from django.utils.translation import gettext as _

from openstack_auth_shib.notifications import notifyProject
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import SUBSCR_WAIT_TYPE
from openstack_auth_shib.notifications import SUBSCR_ONGOING
from openstack_auth_shib.notifications import FIRST_REG_OK_TYPE
from openstack_auth_shib.notifications import FIRST_REG_NO_TYPE
from openstack_auth_shib.notifications import SUBSCR_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_NO_TYPE
from openstack_auth_shib.notifications import SUBSCR_FORCED_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_FORCED_NO_TYPE
from openstack_auth_shib.notifications import PRJ_CREATE_TYPE
from openstack_auth_shib.notifications import PRJ_REJ_TYPE
from openstack_auth_shib.notifications import USER_RENEWED_TYPE
from openstack_auth_shib.notifications import MEMBER_REQUEST
from openstack_auth_shib.notifications import CHANGED_MEMBER_ROLE

from openstack_auth_shib.models import UserMapping
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import NEW_MODEL
if NEW_MODEL:
    from openstack_auth_shib.models import PrjAttribute

from openstack_auth_shib.models import PSTATUS_REG
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_CHK_COMP
from openstack_auth_shib.models import PSTATUS_ADM_ELECT
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import RSTATUS_PENDING
from openstack_auth_shib.models import RSTATUS_REMINDER
from openstack_auth_shib.models import RSTATUS_REMINDACK

from openstack_auth_shib.models import OS_LNAME_LEN
from openstack_auth_shib.models import OS_SNAME_LEN
from openstack_auth_shib.models import PWD_LEN
from openstack_auth_shib.utils import get_prjman_ids
from openstack_auth_shib.utils import TENANTADMIN_ROLE
from openstack_auth_shib.utils import PRJ_REGEX
from openstack_auth_shib.utils import REQID_REGEX
from openstack_auth_shib.utils import setup_new_project
from openstack_auth_shib.utils import add_unit_combos
from openstack_auth_shib.utils import get_year_list
from openstack_auth_shib.utils import FROMNOW
from openstack_auth_shib.utils import ATT_PRJ_EXP
from openstack_auth_shib.utils import get_admin_roleid

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)

def generate_pwd():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(PWD_LEN))
    
def check_and_get_roleids(request):
    tenantadmin_roleid = None
    default_roleid = None
    
    DEFAULT_ROLE = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', None)
    
    for role in keystone_api.role_list(request):
        if role.name == TENANTADMIN_ROLE:
            tenantadmin_roleid = role.id
        elif role.name == DEFAULT_ROLE:
            default_roleid = role.id
    
    if not tenantadmin_roleid:
        #
        # Creation of project-manager role if necessary
        #
        tenantadmin_roleid = keystone_api.role_create(request, TENANTADMIN_ROLE)
        if not tenantadmin_roleid:
            raise Exception("Cannot retrieve tenant admin role id")
    
    if not default_roleid:
        raise Exception("Cannot retrieve default role id")
    
    return (tenantadmin_roleid, default_roleid)


class PreCheckForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(PreCheckForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.IntegerField(widget=HiddenInput)

        self.fields['username'] = forms.CharField(
            label=_("User name"),
            required=True,
            max_length=OS_LNAME_LEN
        )

        init_values = kwargs['initial'] if 'initial' in kwargs else dict()
        if 'extaccount' in init_values and init_values['extaccount']:
            self.fields['username'].widget = forms.TextInput(attrs={'readonly': 'readonly'})
        
        self.expiration = FROMNOW(365)

    def preprocess_prj(self, registr, data):
        pass

    def post_reminder(self, registration, email):
        regReq = RegRequest(
            registration = registration,
            email = email,
            flowstatus = RSTATUS_REMINDER,
            notes = "-"
        )
        regReq.save()

    def clean(self):
        return super(PreCheckForm, self).clean()

    @sensitive_variables('data')
    def handle(self, request, data):

        if not data['username']:
            messages.error(request, _("Cannot process request: missing username"))
            return False
        
        try:
                
            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)

            with transaction.atomic():

                registration = Registration.objects.get(regid=int(data['regid']))

                reg_request = RegRequest.objects.filter(
                    registration=registration,
                    flowstatus=RSTATUS_PENDING
                )[0]
                    
                prjReqList = PrjRequest.objects.filter(registration=registration)

                password = reg_request.password
                if not password:
                    password = generate_pwd()
                
                user_email = reg_request.email

                #
                # Mapping of external accounts
                #
                is_local = True
                if reg_request.externalid:
                    mapping = UserMapping(globaluser=reg_request.externalid,
                                    registration=reg_request.registration)
                    mapping.save()
                    is_local = False
                    LOG.info("Registered external account %s" % reg_request.externalid)
                    
                #
                # Forward request to project administrators
                #
                q_args = {
                    'project__projectid__isnull' : False,
                    'flowstatus' : PSTATUS_REG
                }
                prjReqList.filter(**q_args).update(flowstatus=PSTATUS_PENDING)

                #
                # Creation of new tenants
                #

                self.preprocess_prj(registration, data)

                new_prj_list = list()

                p_reqs = prjReqList.filter(
                    project__projectid__isnull = True,
                    flowstatus = PSTATUS_REG
                )
                if len(p_reqs):
                    newreq_prj = p_reqs[0].project
                    kprj = keystone_api.tenant_create(request, newreq_prj.projectname,
                                                        newreq_prj.description, True)
                    newreq_prj.projectid = kprj.id
                    newreq_prj.save()
                    new_prj_list.append(newreq_prj)

                    setup_new_project(request, kprj.id, newreq_prj.projectname, data)

                    LOG.info("Created tenant %s" % newreq_prj.projectname)
                
                #
                # User creation
                #
                if not registration.userid:
                    
                    if is_local:
                        registration.username = data['username']

                    kuser = keystone_api.user_create(request, 
                                                    name=registration.username,
                                                    password=password,
                                                    email=user_email,
                                                    enabled=True)

                    registration.expdate = self.expiration
                    registration.userid = kuser.id
                    registration.save()
                    LOG.info("Created user %s" % registration.username)

                    mail_obj = EMail()
                    mail_obj.registration = registration
                    mail_obj.email = user_email
                    mail_obj.save()

                #
                # The new user is the project manager of its tenant
                # register the expiration date per tenant
                #
                for prj_item in new_prj_list:

                    expiration = Expiration.objects.create_expiration(
                        registration = registration,
                        project = prj_item,
                        expdate = self.expiration
                    )

                    prjRole = PrjRole()
                    prjRole.registration = registration
                    prjRole.project = prj_item
                    prjRole.roleid = tenantadmin_roleid
                    prjRole.save()

                    keystone_api.add_tenant_user_role(request, prj_item.projectid,
                                            registration.userid, tenantadmin_roleid)

                #
                # Send notifications to project administrators and users
                #
                for p_item in prjReqList.filter(flowstatus=PSTATUS_PENDING):
                
                    m_userids = get_prjman_ids(request, p_item.project.projectid)
                    tmpres = EMail.objects.filter(registration__userid__in=m_userids)
                    m_emails = [ x.email for x in tmpres ]                    

                    noti_params = {
                        'username' : data['username'],
                        'project' : p_item.project.projectname
                    }
                    notifyProject(request=self.request, rcpt=m_emails, action=SUBSCR_WAIT_TYPE, context=noti_params,
                                  dst_project_id=p_item.project.projectid)
                    
                    n2_params = {
                        'username' : p_item.registration.username,
                        'project' : p_item.project.projectname,
                        'prjadmins' : m_emails
                    }

                    notifyUser(request=self.request, rcpt=user_email, action=SUBSCR_ONGOING, context=n2_params,
                               dst_project_id=p_item.project.projectid, dst_user_id=registration.userid)

                newprj_reqs = prjReqList.filter(flowstatus=PSTATUS_REG)
                for p_item in newprj_reqs:
                    noti_params = {
                        'username' : p_item.registration.username,
                        'project' : p_item.project.projectname
                    }
                    notifyUser(request=self.request, rcpt=user_email, action=FIRST_REG_OK_TYPE, context=noti_params,
                               dst_project_id=p_item.project.projectid, dst_user_id=p_item.registration.userid)

                #
                # cache cleanup
                #
                newprj_reqs.delete()
                reg_request.delete()

                self.post_reminder(registration, user_email)

        except:
            LOG.error("Error pre-checking request", exc_info=True)
            messages.error(request, _("Cannot pre-check request"))
            return False

        return True


class GrantAllForm(PreCheckForm):

    def __init__(self, request, *args, **kwargs):
        super(GrantAllForm, self).__init__(request, *args, **kwargs)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            required=True,
            widget=SelectDateWidget(None, get_year_list())
        )

        self.fields['rename'] = forms.CharField(
            label=_('Project name'),
            max_length=OS_SNAME_LEN
        )

        self.fields['newdescr'] = forms.CharField(
            label=_("Project description"),
            required=False,
            widget=forms.widgets.Textarea()
        )

        add_unit_combos(self)

    def preprocess_prj(self, registration, data):

        p_reqs = PrjRequest.objects.filter(
            registration=registration,
            project__projectid__isnull = True,
            flowstatus = PSTATUS_REG
        )
        if len(p_reqs):
            # Assume there's only one request pending
            chk_repl_project(registration.regid,
                             p_reqs[0].project.projectname, data['rename'],
                             p_reqs[0].project.description, data['newdescr'])

    def post_reminder(self, registration, email):
        pass

    def clean(self):
        data = super(GrantAllForm, self).clean()

        tmpm = PRJ_REGEX.search(data['rename'])
        if tmpm:
            raise ValidationError(_('Bad character "%s" for project name.') % tmpm.group(0))

        return data

    @sensitive_variables('data')
    def handle(self, request, data):
        self.expiration = data['expiration']
        return super(GrantAllForm, self).handle(request, data)


class RejectForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(RejectForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.IntegerField(widget=HiddenInput)

        self.fields['reason'] = forms.CharField(
            label=_('Message'),
            required=False,
            widget=forms.widgets.Textarea()
        )


    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:

            with transaction.atomic():
                
                registration = Registration.objects.get(regid=int(data['regid']))
                prjReqList = PrjRequest.objects.filter(registration=registration)
                regReqList = RegRequest.objects.filter(
                    registration=registration,
                    flowstatus=RSTATUS_PENDING
                )

                #
                # Delete request for projects to be created
                #
                newprj_list = list()
                for prj_req in prjReqList:
                    if not prj_req.project.projectid:
                        newprj_list.append(prj_req.project.projectname)
                    
                if len(newprj_list):
                    Project.objects.filter(projectname__in=newprj_list).delete()
                    
                #
                # First registration request, remove all (using cascaded foreign key)
                #
            
                user_email = regReqList[0].email
                user_name = registration.username
                
                registration.delete()
            
                noti_params = {
                    'username': user_name,
                    'projects': list(p.project.projectname for p in prjReqList),
                    'project_creation': (len(newprj_list) != 0),
                    'notes' : data['reason']
                }
                notifyUser(request=self.request, rcpt=user_email, action=FIRST_REG_NO_TYPE, context=noti_params)
            

        except:
            LOG.error("Error rejecting request", exc_info=True)
            messages.error(request, _("Cannot reject request"))
            return False

        return True


class ForcedCheckForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ForcedCheckForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget(None, get_year_list())
        )

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)
            usr_and_prj = REQID_REGEX.search(data['requestid'])

            with transaction.atomic():
                q_args = {
                    'registration__regid' : int(usr_and_prj.group(1)),
                    'project__projectname' : usr_and_prj.group(2)
                }
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                
                #
                # Insert expiration date per tenant
                #
                expiration = Expiration.objects.create_expiration(
                    registration = prj_req.registration,
                    project = prj_req.project,
                    expdate = data['expiration']
                )

                project_name = prj_req.project.projectname
                project_id = prj_req.project.projectid
                user_name = prj_req.registration.username
                user_id = prj_req.registration.userid
                
                keystone_api.add_tenant_user_role(request, project_id,
                                                user_id, default_roleid)

                #
                # Enable reminder for cloud admin
                #
                RegRequest.objects.filter(
                    registration = prj_req.registration,
                    flowstatus = RSTATUS_REMINDER
                ).update(flowstatus = RSTATUS_REMINDACK)

                #
                # clear request
                #
                prj_req.delete()

            #
            # send notification to project managers and users
            #
            tmpres = EMail.objects.filter(registration__userid=user_id)
            user_email = tmpres[0].email if tmpres else None
            
            m_userids = get_prjman_ids(request, project_id)
            tmpres = EMail.objects.filter(registration__userid__in=m_userids)
            m_emails = [ x.email for x in tmpres ]

            noti_params = {
                'username' : user_name,
                'project' : project_name
            }

            notifyProject(request=self.request, rcpt=m_emails, action=SUBSCR_FORCED_OK_TYPE, context=noti_params,
                          dst_project_id=project_id)
            notifyUser(request=self.request, rcpt=user_email, action=SUBSCR_OK_TYPE, context=noti_params,
                       dst_project_id=project_id, dst_user_id=user_id)
                
        except:
            LOG.error("Error forced-checking request", exc_info=True)
            messages.error(request, _("Cannot forced check request"))
            return False

        return True


class ForcedRejectForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ForcedRejectForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

        self.fields['reason'] = forms.CharField(
            label=_('Message'),
            required=False,
            widget=forms.widgets.Textarea()
        )

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)
            usr_and_prj = REQID_REGEX.search(data['requestid'])

            with transaction.atomic():
                q_args = {
                    'registration__regid' : int(usr_and_prj.group(1)),
                    'project__projectname' : usr_and_prj.group(2)
                }
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                

                project_name = prj_req.project.projectname
                project_id = prj_req.project.projectid
                user_name = prj_req.registration.username
                user_id = prj_req.registration.userid
                
                #
                # clear request
                #
                prj_req.delete()

            #
            # send notification to project managers and users
            #
            tmpres = EMail.objects.filter(registration__userid=user_id)
            user_email = tmpres[0].email if tmpres else None
            
            m_userids = get_prjman_ids(request, project_id)
            tmpres = EMail.objects.filter(registration__userid__in=m_userids)
            m_emails = [ x.email for x in tmpres ]

            noti_params = {
                'username' : user_name,
                'project' : project_name,
                'notes' : data['reason']
            }

            notifyProject(request=self.request, rcpt=m_emails, action=SUBSCR_FORCED_NO_TYPE, context=noti_params,
                          dst_project_id=project_id)
            notifyUser(request=self.request, rcpt=user_email, action=SUBSCR_NO_TYPE, context=noti_params,
                       dst_project_id=project_id, dst_user_id=user_id)
                
        except:
            LOG.error("Error forced-checking request", exc_info=True)
            messages.error(request, _("Cannot forced check request"))
            return False

        return True


class NewProjectCheckForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(NewProjectCheckForm, self).__init__(request, *args, **kwargs)

        self.fields['newname'] = forms.CharField(
            label=_('Project name'),
            max_length=OS_SNAME_LEN
        )

        self.fields['newdescr'] = forms.CharField(
            label=_("Project description"),
            required=False,
            widget=forms.widgets.Textarea()
        )

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Administrator expiration date"),
            widget=SelectDateWidget(None, get_year_list())
        )

        add_unit_combos(self)

    def clean(self):
        data = super(NewProjectCheckForm, self).clean()

        tmpm = PRJ_REGEX.search(data['newname'])
        if tmpm:
            raise ValidationError(_('Bad character %s for project name.') % tmpm.group(0))

        return data

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:

            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)
            usr_and_prj = REQID_REGEX.search(data['requestid'])

            with transaction.atomic():

                regid, prjname = chk_repl_project(int(usr_and_prj.group(1)),
                                                  usr_and_prj.group(2), data['newname'],
                                                  None, data['newdescr'])

                #
                # Creation of new tenant
                #
                prj_req = PrjRequest.objects.filter(
                    registration__regid = regid,
                    project__projectname = prjname
                )[0]
                
                project_name = prj_req.project.projectname
                user_id = prj_req.registration.userid
                
                kprj = keystone_api.tenant_create(request, project_name,
                                                    prj_req.project.description, True)
                prj_req.project.projectid = kprj.id
                prj_req.project.save()
                LOG.info("Created tenant %s" % project_name)
                
                #
                # The new user is the project manager of its tenant
                #
                prjRole = PrjRole()
                prjRole.registration = prj_req.registration
                prjRole.project = prj_req.project
                prjRole.roleid = tenantadmin_roleid
                prjRole.save()

                keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                user_id, tenantadmin_roleid)


                #
                # Insert expiration date per tenant
                #
                expiration = Expiration.objects.create_expiration(
                    registration = prj_req.registration,
                    project = prj_req.project,
                    expdate = data['expiration']
                )

                #
                # Clear request
                #
                prj_req.delete()
                
                setup_new_project(request, kprj.id, project_name, data)

            #
            # Send notification to the user
            #
            tmpres = EMail.objects.filter(registration__userid=user_id)
            user_email = tmpres[0].email if tmpres else None

            noti_params = {
                'project' : project_name
            }

            notifyUser(request=self.request, rcpt=user_email, action=PRJ_CREATE_TYPE, context=noti_params,
                       dst_project_id=kprj.id, dst_user_id=user_id)

        except:
            LOG.error("Error pre-checking project", exc_info=True)
            messages.error(request, _("Cannot pre-check project"))
            return False

        return True


class NewProjectRejectForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(NewProjectRejectForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

        self.fields['reason'] = forms.CharField(
            label=_('Message'),
            required=False,
            widget=forms.widgets.Textarea()
        )


    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:

            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)
            usr_and_prj = REQID_REGEX.search(data['requestid'])

            with transaction.atomic():

                #
                # Creation of new tenant
                #
                q_args = {
                    'registration__regid' : int(usr_and_prj.group(1)),
                    'project__projectname' : usr_and_prj.group(2)
                }
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                
                project_name = prj_req.project.projectname
                user_id = prj_req.registration.userid
                
                #
                # Clear request
                #
                prj_req.delete()
                
            #
            # Send notification to the user
            #
            tmpres = EMail.objects.filter(registration__userid=user_id)
            user_email = tmpres[0].email if tmpres else None

            noti_params = {
                'project' : project_name,
                'notes' : data['reason']
            }

            notifyUser(request=self.request, rcpt=user_email, action=PRJ_REJ_TYPE, context=noti_params,
                       dst_user_id=user_id)

        except:
            LOG.error("Error pre-checking project", exc_info=True)
            messages.error(request, _("Cannot pre-check project"))
            return False

        return True


class RenewAdminForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(RenewAdminForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget(None, get_year_list())
        )

    @sensitive_variables('data')
    def handle(self, request, data):

        try:

            u_infos = list()

            usr_and_prj = REQID_REGEX.search(data['requestid'])
            regid = int(usr_and_prj.group(1))
            prjname = usr_and_prj.group(2)

            with transaction.atomic():

                prj_reqs = PrjRequest.objects.filter(
                    registration__regid = regid,
                    project__projectname = prjname,
                    flowstatus__in = [ PSTATUS_RENEW_ADMIN, PSTATUS_RENEW_MEMB ]
                )
                
                if len(prj_reqs) == 0:
                    return True
                
                # renew admin and forced-renew normal member
                if NEW_MODEL and prj_reqs[0].flowstatus == PSTATUS_RENEW_ADMIN:
                    # Renew all project admins
                    for role in PrjRole.objects.filter(project__projectname = prjname):
                        Expiration.objects.update_expiration(
                            registration = role.registration,
                            project = role.project,
                            expdate=data['expiration']
                        )
                    tmpres = EMail.objects.filter(registration=role.registration)
                    if len(tmpres) > 0:
                        u_infos.append((role.registration.username, role.registration.userid,
                                        tmpres[0].email))

                    PrjRequest.objects.filter(
                        project = role.project,
                        flowstatus = PSTATUS_RENEW_ADMIN
                    ).delete()

                    PrjAttribute.objects.filter(
                        project = role.project,
                        name = ATT_PRJ_EXP
                    ).update(value = datetime.isoformat(data['expiration']))

                else:
                    Expiration.objects.update_expiration(
                        registration__regid = regid,
                        project__projectname = prjname,
                        expdate=data['expiration']
                    )

                    user_reg = prj_reqs[0].registration
                    tmpres = EMail.objects.filter(registration=user_reg)
                    if len(tmpres) > 0:
                        u_infos.append((user_reg.username, user_reg.userid, tmpres[0].email))
                    #
                    # Clear requests
                    #
                    prj_reqs.delete()

            #
            # send notification to the project admin
            #
            for uname, uid, email in u_infos:
                noti_params = {
                    'username' : uname,
                    'project' : prjname,
                    'expiration' : data['expiration'].strftime("%d %B %Y")
                }

                notifyUser(request=request, rcpt=email, action=USER_RENEWED_TYPE,
                           context=noti_params, dst_user_id=uid)

        except:
            LOG.error("Cannot renew project admin", exc_info=True)
            messages.error(request, _("Cannot renew project admin"))
            return False
        
        return True

class DetailsForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(DetailsForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

    @sensitive_variables('data')
    def handle(self, request, data):
        return True

class RemainderAckForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(RemainderAckForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

    @sensitive_variables('data')
    def handle(self, request, data):

        with transaction.atomic():
            usr_and_prj = REQID_REGEX.search(data['requestid'])
            RegRequest.objects.filter(
                registration__regid = int(usr_and_prj.group(1)),
                flowstatus = RSTATUS_REMINDACK
            ).delete()

        return True

class CompAckForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(CompAckForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

    @sensitive_variables('data')
    def handle(self, request, data):

        admin_emails = list()

        with transaction.atomic():
            usr_and_prj = REQID_REGEX.search(data['requestid'])

            project = Project.objects.get(projectname = usr_and_prj.group(2))
            PrjRequest.objects.filter(
                registration__regid = int(usr_and_prj.group(1)),
                project = project,
                flowstatus = PSTATUS_CHK_COMP
            ).update(flowstatus = PSTATUS_PENDING)

            for prj_role in PrjRole.objects.filter(project = project):
                for email_obj in EMail.objects.filter(registration = prj_role.registration):
                    admin_emails.append(email_obj.email)

        notifyProject(request = request,
                      rcpt = admin_emails,
                      action = MEMBER_REQUEST,
                      context = {'username' : request.user.username,
                                'project' : project.projectname})
        return True

class PromoteAdminForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(PromoteAdminForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

    @sensitive_variables('data')
    def handle(self, request, data):
        usr_and_prj = REQID_REGEX.search(data['requestid'])
        t_admin_roleid = get_admin_roleid(request)
        user_email = None
        noti_params = dict()

        with transaction.atomic():
            prj_reqs = PrjRequest.objects.filter(
                registration__regid = int(usr_and_prj.group(1)),
                project__projectname = usr_and_prj.group(2),
                flowstatus = PSTATUS_ADM_ELECT
            )
            if len(prj_reqs) == 0:
                return False

            registration = prj_reqs[0].registration
            project = prj_reqs[0].project
            PrjRole(
                registration = registration,
                project = project,
                roleid = t_admin_roleid
            ).save()
            
            tmpl = EMail.objects.filter(registration = registration)
            if tmpl:
                user_email = tmpl[0]

            if NEW_MODEL:
                tmpl = PrjAttribute.objects.filter(
                    project = project,
                    name = ATT_PRJ_EXP
                )
                if len(tmpl) > 0:
                    Expiration.objects.filter(
                        registration = registration,
                        project = project,
                    ).update(expdate = datetime.fromisoformat(tmpl[0].value))

            prj_reqs.delete()

            keystone_api.add_tenant_user_role(request,
                role = t_admin_roleid,
                project = project.projectid,
                user = registration.userid
            )

            noti_params['username'] = registration.username
            noti_params['project'] = project.projectname
            noti_params['s_role'] = _("member")
            noti_params['d_role'] = _("project administrator")

        if user_email:
            notifyUser(request = request, rcpt = user_email, action = CHANGED_MEMBER_ROLE,
                        context = noti_params)
        return True

#
# Fix for https://issues.infn.it/jira/browse/PDCL-690
#         https://issues.infn.it/jira/browse/PDCL-1035
#
def chk_repl_project(regid, old_prjname, new_prjname, old_descr, new_descr):

    old_prjreq = None
    q_args = {'registration__regid' : regid, 'project__projectname' : old_prjname}
    if not old_descr:
        old_prjreq = PrjRequest.objects.filter(**q_args)[0]
        old_descr = old_prjreq.project.description

    same_name = not new_prjname or len(new_prjname.strip()) == 0 or old_prjname == new_prjname
    same_descr = not new_descr or len(new_descr.strip()) == 0 or old_descr == new_descr
    if same_name and same_descr:
        return (regid, old_prjname)

    if not old_prjreq:
        old_prjreq = PrjRequest.objects.filter(**q_args)[0]
    old_prj = old_prjreq.project

    if not same_name:
        LOG.info("Change project name %s into %s" % (old_prjname, new_prjname))
        new_prj = Project.objects.create(
            projectname = new_prjname,
            description = old_descr if same_descr else new_descr,
            status = old_prj.status
        )

        new_prjreq = PrjRequest.objects.create(
            registration = old_prjreq.registration,
            project = new_prj,
            notes = old_prjreq.notes
        )

        old_prj.delete()
        return (regid, new_prjname)

    if not same_descr:
        LOG.info("Change description %s into %s for %s" % (old_descr, new_descr, new_prjname))
        old_prj.description = new_descr
        old_prj.save()

    return (regid, new_prjname)



