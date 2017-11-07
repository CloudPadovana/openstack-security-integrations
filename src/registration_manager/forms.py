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
import logging
import base64
from datetime import datetime, timedelta

from Crypto import __version__ as crypto_version
if crypto_version.startswith('2.0'):
    from Crypto.Util import randpool
else:
    from Crypto import Random

from horizon import forms
from horizon import messages

from django.db import transaction
from django.conf import settings
from django.forms.widgets import HiddenInput
from django.forms.extras.widgets import SelectDateWidget
from django.views.decorators.debug import sensitive_variables
from django.utils.translation import ugettext as _

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

from openstack_auth_shib.models import UserMapping
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole

from openstack_auth_shib.models import PSTATUS_REG
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PRJ_GUEST

from openstack_auth_shib.models import OS_LNAME_LEN
from openstack_auth_shib.utils import get_prjman_ids
from openstack_auth_shib.utils import TENANTADMIN_ROLE

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)

def generate_pwd():
    if crypto_version.startswith('2.0'):
        prng = randpool.RandomPool()
        iv = prng.get_bytes(256)
    else:
        prng = Random.new()
        iv = prng.read(16)
    return base64.b64encode(iv)
    
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
        
        self.expiration = datetime.now() + timedelta(365)

    @sensitive_variables('data')
    def handle(self, request, data):

        if not data['username']:
            messages.error(request, _("Cannot process request: missing username"))
            return False
        
        try:
                
            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)

            with transaction.atomic():

                registration = Registration.objects.get(regid=int(data['regid']))

                reg_request = RegRequest.objects.filter(registration=registration)[0]
                    
                prjReqList = PrjRequest.objects.filter(registration=registration)

                password = reg_request.password
                if not password:
                    password = generate_pwd()
                
                user_email = reg_request.email

                #
                # Mapping of external accounts
                #                
                if reg_request.externalid:
                    mapping = UserMapping(globaluser=reg_request.externalid,
                                    registration=reg_request.registration)
                    mapping.save()
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
                new_prj_list = list()
                q_args = {
                    'project__projectid__isnull' : True,
                    'flowstatus' : PSTATUS_REG
                }
                
                for p_reqs in prjReqList.filter(**q_args):
                    kprj = keystone_api.tenant_create(request, p_reqs.project.projectname,
                                                        p_reqs.project.description, True)
                    p_reqs.project.projectid = kprj.id
                    p_reqs.project.save()
                    new_prj_list.append(p_reqs.project)
                    LOG.info("Created tenant %s" % p_reqs.project.projectname)
                
                #
                # User creation
                #
                if not registration.userid:
                    
                    kuser = keystone_api.user_create(request, 
                                                    name=registration.username,
                                                    password=password,
                                                    email=user_email,
                                                    enabled=True)
                        
                    registration.username = data['username']
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

                    expiration = Expiration()
                    expiration.registration = registration
                    expiration.project = prj_item
                    expiration.expdate = self.expiration
                    expiration.save()

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
                        'project' : p_item.project.projectname,
                        'prjadmins' : m_emails
                    }

                    notifyUser(request=self.request, rcpt=user_email, action=SUBSCR_ONGOING, context=n2_params,
                               dst_project_id=p_item.project.projectid, dst_user_id=registration.userid)

                newprj_reqs = prjReqList.filter(flowstatus=PSTATUS_REG)
                for p_item in newprj_reqs:
                    noti_params = {
                        'username' : p_item.registration.username,
                        'project' : p_item.project.projectname,
                        'guestmode' : False
                    }
                    notifyUser(request=self.request, rcpt=user_email, action=FIRST_REG_OK_TYPE, context=noti_params,
                               dst_project_id=p_item.project.projectid, dst_user_id=p_item.registration.userid)

                #
                # cache cleanup
                #
                newprj_reqs.delete()
                reg_request.delete()

        except:
            LOG.error("Error pre-checking request", exc_info=True)
            messages.error(request, _("Cannot pre-check request"))
            return False

        return True


class GrantAllForm(PreCheckForm):

    def __init__(self, request, *args, **kwargs):
        super(GrantAllForm, self).__init__(request, *args, **kwargs)

        curr_year = datetime.now().year            
        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            required=True,
            widget=SelectDateWidget(None, range(curr_year, curr_year + 25))
        )

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
                regReqList = RegRequest.objects.filter(registration=registration)
                    
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
                
                registration.delete()
            
                noti_params = {
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

        curr_year = datetime.now().year
        years_list = range(curr_year, curr_year+25)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget(None, years_list)
        )

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)
            usr_and_prj = data['requestid'].split(':')

            with transaction.atomic():
                q_args = {
                    'registration__regid' : int(usr_and_prj[0]),
                    'project__projectname' : usr_and_prj[1]
                }
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                
                #
                # Insert expiration date per tenant
                #
                expiration = Expiration()
                expiration.registration = prj_req.registration
                expiration.project = prj_req.project
                expiration.expdate = data['expiration']
                expiration.save()

                #
                # Update the max expiration per user
                #
                user_reg = prj_req.registration
                if data['expiration'] > user_reg.expdate:
                    user_reg.expdate = data['expiration']
                    user_reg.save()

                project_name = prj_req.project.projectname
                project_id = prj_req.project.projectid
                user_name = prj_req.registration.username
                user_id = prj_req.registration.userid
                
                keystone_api.add_tenant_user_role(request, project_id,
                                                user_id, default_roleid)

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
            usr_and_prj = data['requestid'].split(':')

            with transaction.atomic():
                q_args = {
                    'registration__regid' : int(usr_and_prj[0]),
                    'project__projectname' : usr_and_prj[1]
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

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

        curr_year = datetime.now().year
        years_list = range(curr_year, curr_year+25)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget(None, years_list)
        )


    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:

            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)
            usr_and_prj = data['requestid'].split(':')

            with transaction.atomic():

                #
                # Creation of new tenant
                #
                q_args = {
                    'registration__regid' : int(usr_and_prj[0]),
                    'project__projectname' : usr_and_prj[1]
                }
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                
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
                expiration = Expiration()
                expiration.registration = prj_req.registration
                expiration.project = prj_req.project
                expiration.expdate = data['expiration']
                expiration.save()

                #
                # Update the max expiration per user
                #
                user_reg = prj_req.registration
                if data['expiration'] > user_reg.expdate:
                    user_reg.expdate = data['expiration']
                    user_reg.save()

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
            usr_and_prj = data['requestid'].split(':')

            with transaction.atomic():

                #
                # Creation of new tenant
                #
                q_args = {
                    'registration__regid' : int(usr_and_prj[0]),
                    'project__projectname' : usr_and_prj[1]
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


class GuestCheckForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(GuestCheckForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.IntegerField(widget=HiddenInput)

        self.fields['username'] = forms.CharField(
            label=_("User name"),
            required=False,
            max_length=OS_LNAME_LEN
        )

        curr_year = datetime.now().year            
        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            required=False,
            widget=SelectDateWidget(None, range(curr_year, curr_year + 25))
        )

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:

            tenantadmin_roleid, default_roleid = check_and_get_roleids(request)

            with transaction.atomic():
            
                registration = Registration.objects.get(regid=int(data['regid']))

                reg_request = RegRequest.objects.filter(registration=registration)[0]
                
                q_args = {
                    'registration' : registration,
                    'project__status' : PRJ_GUEST
                }
                prj_reqs = PrjRequest.objects.filter(**q_args)
                project_id = prj_reqs[0].project.projectid
                project_name = prj_reqs[0].project.projectname

                password = reg_request.password
                if not password:
                    password = generate_pwd()
                
                user_email = reg_request.email

                #
                # Mapping of external accounts
                #                
                if reg_request.externalid:
                    mapping = UserMapping(globaluser=reg_request.externalid,
                                    registration=reg_request.registration)
                    mapping.save()
                    LOG.info("Registered external account %s" % reg_request.externalid)

                #
                # Insert expiration date per tenant
                #
                expiration = Expiration()
                expiration.registration = prj_reqs[0].registration
                expiration.project = prj_reqs[0].project
                expiration.expdate = data['expiration']
                expiration.save()

                #
                # clear requests
                #
                prj_reqs.delete()
                reg_request.delete()

                #
                # User creation
                # 
                kuser = keystone_api.user_create(request, 
                                                name=registration.username,
                                                password=password,
                                                email=user_email,
                                                enabled=True)
                    
                registration.username = data['username']
                registration.expdate = data['expiration']
                registration.userid = kuser.id
                registration.save()
                LOG.info("Created guest user %s" % registration.username)

                keystone_api.add_tenant_user_role(request, project_id,
                                            registration.userid, default_roleid)

                #
                # Send notification to the user
                #
                noti_params = {
                    'username' : registration.username,
                    'project' : project_name,
                    'guestmode' : True
                }
                notifyUser(request=self.request, rcpt=user_email, action=FIRST_REG_OK_TYPE, context=noti_params,
                           dst_project_id=project_id, dst_user_id=registration.userid)

        except:
            LOG.error("Error pre-checking project", exc_info=True)
            messages.error(request, _("Cannot pre-check project"))
            return False

        return True


class RenewAdminForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(RenewAdminForm, self).__init__(request, *args, **kwargs)

        self.fields['requestid'] = forms.CharField(widget=HiddenInput)

        curr_year = datetime.now().year
        years_list = range(curr_year, curr_year + 25)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget(None, years_list)
        )

    @sensitive_variables('data')
    def handle(self, request, data):

        try:
        
            with transaction.atomic():

                usr_and_prj = data['requestid'].split(':')
                regid = int(usr_and_prj[0])

                prj_reqs = PrjRequest.objects.filter(
                    registration__regid = regid,
                    project__projectname = usr_and_prj[1],
                    flowstatus = PSTATUS_RENEW_ADMIN
                )
                
                if len(prj_reqs) == 0:
                    return True
                
                prj_exp = Expiration.objects.filter(
                    registration__regid = regid,
                    project__projectname = usr_and_prj[1]
                )
                prj_exp.update(expdate=data['expiration'])
                
                #
                # Update the max expiration per user
                #
                user_reg = Registration.objects.get(regid=regid)
                if data['expiration'] > user_reg.expdate:
                    user_reg.expdate = data['expiration']
                    user_reg.save()

                #
                # Clear requests
                #
                prj_reqs.delete()
                
                
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


