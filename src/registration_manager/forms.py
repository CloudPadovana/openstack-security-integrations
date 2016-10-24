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
import datetime

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

from openstack_auth_shib.notifications import notification_render
from openstack_auth_shib.notifications import notify as notifyUsers
from openstack_auth_shib.notifications import SUBSCR_WAIT_TYPE
from openstack_auth_shib.notifications import SUBSCR_ONGOING
from openstack_auth_shib.notifications import FIRST_REG_OK_TYPE
from openstack_auth_shib.notifications import FIRST_REG_NO_TYPE
from openstack_auth_shib.notifications import SUBSCR_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_NO_TYPE
from openstack_auth_shib.notifications import SUBSCR_FORCED_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_FORCED_NO_TYPE

from openstack_auth_shib.models import UserMapping
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PSTATUS_REG
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_APPR
from openstack_auth_shib.models import PSTATUS_REJ

from openstack_auth_shib.models import RSTATUS_PENDING
from openstack_auth_shib.models import RSTATUS_PRECHKD
from openstack_auth_shib.models import RSTATUS_CHECKED
from openstack_auth_shib.models import RSTATUS_NOFLOW

from openstack_auth_shib.models import OS_LNAME_LEN
from openstack_auth_shib.utils import get_project_managers
from openstack_auth_shib.utils import TENANTADMIN_ROLE

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)

class ProjectResultInfo():

    def __init__(self, name, res_code):
        self.name = name
        self.code = res_code
    
    def appr(self):
        return self.code == 'a'
    
    def rej(self):
        return self.code == 'r'
    
    def new(self):
        return self.code == 'c'

class ProcessRegForm(forms.SelfHandlingForm):

    checkaction = forms.CharField(widget=HiddenInput, initial='accept')
    
    def __init__(self, request, *args, **kwargs):
        super(ProcessRegForm, self).__init__(request, *args, **kwargs)
        
        self.fields['regid'] = forms.IntegerField(widget=HiddenInput)
        self.fields['processinglevel'] = forms.IntegerField(widget=HiddenInput)
        
        flowstatus = kwargs['initial']['processinglevel']
        if flowstatus == RSTATUS_PENDING or flowstatus == RSTATUS_NOFLOW:
            self.fields['username'] = forms.CharField(
                label=_("User name"),
                required=False,
                max_length=OS_LNAME_LEN
            )
            
            curr_year = datetime.datetime.now().year
            years_list = range(curr_year, curr_year+25)
                
            self.fields['expiration'] = forms.DateTimeField(
                label=_("Expiration date"),
                required=False,
                initial=datetime.datetime.now() + datetime.timedelta(365),
                widget=SelectDateWidget(None, years_list)
            )
        else:
            self.fields['username'] = forms.CharField(
                label=_("User name"),
                required=False,
                widget = forms.TextInput(attrs={'readonly': 'readonly'})
            )
            
        self.fields['reason'] = forms.CharField(
            label=_('Message'),
            required=False,
            widget=forms.widgets.Textarea()
        )

    def _check_and_get_roleids(self, request):
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

    def _generate_pwd(self):
        if crypto_version.startswith('2.0'):
            prng = randpool.RandomPool()
            iv = prng.get_bytes(256)
        else:
            prng = Random.new()
            iv = prng.read(16)
        return base64.b64encode(iv)
    
    def _convert_domain(self, request, domain_name):
        for ditem in keystone_api.domain_list(request):
            if ditem.name == domain_name:
                return ditem.id
        return None
    
    def _retrieve_email(self, request, uid):
        try:
            tmpusr = keystone_api.user_get(request, uid)
            return tmpusr.email
        except:
            LOG.error("Cannot retrieve email", exc_info=True)
        return None

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
            if data['checkaction'] == 'accept':
                self._handle_accept(request, data)
            else:
                self._handle_reject(request, data)
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            messages.error(request, exc_value)
            return False

        return True



    def _handle_accept(self, request, data):
    
        with transaction.atomic():
            
            registration = Registration.objects.get(regid=int(data['regid']))
            flowstatus = int(data['processinglevel'])
            
            userReqList = RegRequest.objects.filter(registration=registration)
                
            prjReqList = PrjRequest.objects.filter(registration=registration)
            
            #
            # get email first from registration request
            # and then from keystone (user must be already registered)
            #
            email = None
            for tmpReq in userReqList:
                if not email:
                    email = tmpReq.email
            
            if not email:
                email = self._retrieve_email(request, registration.userid)
                    
            if flowstatus == RSTATUS_PENDING or flowstatus == RSTATUS_NOFLOW:
                #
                # User renaming
                #
                if registration.userid == None:
                
                    if not data['username']:
                        raise Exception(_("Cannot process request: missing username"))
                    if not data['expiration']:
                        raise Exception(_("Cannot process request: missing expiration date"))
                    
                    registration.username = data['username']
                    registration.expdate = data['expiration']
                    registration.save()
                
                userReqList.update(flowstatus=RSTATUS_CHECKED)
                
            if flowstatus == RSTATUS_PENDING or flowstatus == RSTATUS_PRECHKD \
                 or flowstatus == RSTATUS_NOFLOW:
                #
                # Send request to prj-admin
                #
                q_args = {
                    'project__projectid__isnull' : False,
                    'flowstatus' : PSTATUS_REG
                }
                prjReqList.filter(**q_args).update(flowstatus=PSTATUS_PENDING)
                
                q_args['flowstatus'] = PSTATUS_PENDING
                for p_item in prjReqList.filter(**q_args):
                
                    m_users = get_project_managers(request, p_item.project.projectid)
                    m_emails = [ usr.email for usr in m_users ]
                    
                    noti_params = {
                        'username' : registration.username,
                        'project' : p_item.project.projectname
                    }
                    noti_sbj, noti_body = notification_render(SUBSCR_WAIT_TYPE, noti_params)
                    notifyUsers(m_emails, noti_sbj, noti_body)
                    
                    if email:
                        n2_params = {
                            'project' : p_item.project.projectname,
                            'prjadmins' : m_emails
                        }
                        noti_sbj, noti_body = notification_render(SUBSCR_ONGOING, n2_params)
                        notifyUsers(email, noti_sbj, noti_body)
                    
            if flowstatus == RSTATUS_CHECKED or flowstatus == RSTATUS_NOFLOW:
                main_tenant = None
                password = None
                first_registr = False
                
                domain_id = self._convert_domain(request, registration.domain)

                #
                # Mapping of external accounts
                #                
                for tmpReq in userReqList:
                    if tmpReq.externalid:
                        LOG.debug("Registering external account %s" % tmpReq.externalid)
                        mapping = UserMapping(globaluser=tmpReq.externalid,
                                        registration=tmpReq.registration)
                        mapping.save()
                        
                    if not password:
                        password = tmpReq.password
                    
                #
                # Registration of the new tenants
                #
                prjs_to_create = list()
                prjs_approved = list()
                prjs_rejected = list()
                
                for prj_req in prjReqList:
                    
                    if not prj_req.project.projectid:
                        
                        prjs_to_create.append(prj_req)
                        if not main_tenant:
                            main_tenant = prj_req.project
                    
                    elif prj_req.flowstatus == PSTATUS_APPR:
                    
                        prjs_approved.append(prj_req)
                        if not main_tenant:
                            main_tenant = prj_req.project
                            
                    elif prj_req.flowstatus == PSTATUS_REJ:
                    
                        prjs_rejected.append(prj_req)
                        
                    else:
                        raise Exception(_("Cannot process request: pending projects"))
                    
                for prj_req in prjs_to_create:
                    LOG.debug("Creating tenant %s" % prj_req.project.projectname)
                    kprj = keystone_api.tenant_create(request, prj_req.project.projectname,
                        prj_req.project.description, True, domain_id)
                            
                    prj_req.project.projectid = kprj.id
                    prj_req.project.save()
                    
                #
                # User creation
                #
                if not registration.userid:
                    
                    if not main_tenant:
                        raise Exception(_("No tenants for first registration"))
                        
                    if not email:
                        raise Exception( _("No email for first registration"))
                        
                    if not password:
                        password = self._generate_pwd()
                        
                    kuser = keystone_api.user_create(request, 
                                                    name=registration.username,
                                                    password=password,
                                                    email=email,
                                                    project=main_tenant.projectid,
                                                    enabled=True, domain=domain_id)
                        
                    registration.userid = kuser.id
                    registration.save()
                    first_registr = True
                    
                tenantadmin_roleid, default_roleid = self._check_and_get_roleids(request)
                
                prj_infos = list()

                #
                # Use default member role for approved subscriptions
                # Use tenant admin role for new created projects
                #
                for prj_req in prjs_approved:
                    keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, default_roleid)
                    prj_infos.append(ProjectResultInfo(prj_req.project.projectname, 'a'))
                    
                for prj_req in prjs_to_create:
                    keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, tenantadmin_roleid)

                    prj_infos.append(ProjectResultInfo(prj_req.project.projectname, 'c'))
                    
                for prj_req in prjs_rejected:
                    prj_infos.append(ProjectResultInfo(prj_req.project.projectname, 'r'))
                
                
                noti_params = {
                    'username' : registration.username,
                    'projects_info' : prj_infos
                }
                
                if first_registr:
                    
                    noti_sbj, noti_body = notification_render(FIRST_REG_OK_TYPE, noti_params)
                    notifyUsers(email, noti_sbj, noti_body)
                    
                elif len(prjs_approved) + len(prjs_rejected) + len(prjs_to_create) > 0:
                
                    noti_sbj, noti_body = notification_render(SUBSCR_OK_TYPE, noti_params)
                    notifyUsers(email, noti_sbj, noti_body)
                
                #
                # cache cleanup
                #
                prjReqList.delete()
                userReqList.delete()
                
    def _handle_reject(self, request, data):
            
        all_prj_req = list()
        recipients = None
        first_reg_rej = False

        with transaction.atomic():
            
            registration = Registration.objects.get(regid=int(data['regid']))
            prjReqList = PrjRequest.objects.filter(registration=registration)
            regReqList = RegRequest.objects.filter(registration=registration)
                
            #
            # Delete projects to be created
            #
            newprj_list = list()
            for prj_req in prjReqList:
                all_prj_req.append(prj_req.project.projectname)
                if not prj_req.project.projectid:
                    newprj_list.append(prj_req.project.projectname)
                
            if len(newprj_list):
                Project.objects.filter(projectname__in=newprj_list).delete()
                
            if registration.userid:
                
                prjReqList.delete()
                    
                regReqList.delete()
                
                recipients = self._retrieve_email(request, registration.userid)
                    
            else:
            
                recipients = [ x for x in regReqList.values_list('email', flat=True) ]
                
                registration.delete()
                first_reg_rej = True
        
        if first_reg_rej:
        
            noti_params = {
                'notes' : data['reason']
            }
            noti_sbj, noti_body = notification_render(FIRST_REG_NO_TYPE, noti_params)
            notifyUsers(recipients, noti_sbj, noti_body)
        
        elif all_prj_req:
            noti_params = {
                'projects_rejected' : all_prj_req
            }
            noti_sbj, noti_body = notification_render(SUBSCR_NO_TYPE, noti_params)
            notifyUsers(recipients, noti_sbj, noti_body)


class ForceApproveForm(forms.SelfHandlingForm):

    regid = forms.IntegerField(label=_("ID"), widget=HiddenInput)

    def __init__(self, request, *args, **kwargs):
        super(ForceApproveForm, self).__init__(request, *args, **kwargs)
        
        regid = int(kwargs['initial']['regid'])
        q_args = {
            'registration__regid' : regid,
            'flowstatus' : PSTATUS_PENDING
        }
        pendProjects = PrjRequest.objects.filter(**q_args)

        self.prjcache = dict()
        self.username = None
        for p_item in pendProjects:
        
            prjname = p_item.project.projectname
            prjid = p_item.project.projectid
            self.prjcache[prjid] = prjname
            if not self.username:
                self.username = p_item.registration.username
            
            self.fields['project_%s' % prjid] = forms.ChoiceField(
                label=prjname,
                required=False,
                widget=forms.Select(),
                choices=[
                    (PSTATUS_PENDING, _('Keep pending')),
                    (PSTATUS_APPR, _('Approve')),
                    (PSTATUS_REJ, _('Reject'))
                ]
            )
    
    @sensitive_variables('data')
    def handle(self, request, data):
    
        accpt_prjs = list()
        rej_prjs = list()
        
        for key in data:
            if key.startswith('project_'):
                p_id = key[8:]
                pstatus = int(data[key])
                if pstatus == PSTATUS_APPR and p_id in self.prjcache:
                    accpt_prjs.append(p_id)
                elif pstatus == PSTATUS_REJ and p_id in self.prjcache:
                    rej_prjs.append(p_id)
        
        with transaction.atomic():
            
            if len(accpt_prjs):
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectid__in' : accpt_prjs
                }
                PrjRequest.objects.filter(**q_args).update(flowstatus=PSTATUS_APPR)

            if len(rej_prjs):
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectid__in' : rej_prjs
                }
                PrjRequest.objects.filter(**q_args).update(flowstatus=PSTATUS_REJ)


        for prjid in accpt_prjs:
            m_users = get_project_managers(request, prjid)
            noti_params = {
                'username' : self.username,
                'project' : self.prjcache[prjid]
            }
            noti_sbj, noti_body = notification_render(SUBSCR_FORCED_OK_TYPE, noti_params)
            notifyUsers([ usr.email for usr in m_users ], noti_sbj, noti_body)

        for prjid in rej_prjs:
            m_users = get_project_managers(request, prjid)
            noti_params = {
                'username' : self.username,
                'project' : self.prjcache[prjid]
            }
            noti_sbj, noti_body = notification_render(SUBSCR_FORCED_NO_TYPE, noti_params)
            notifyUsers([ usr.email for usr in m_users ], noti_sbj, noti_body)

        return True

###############################################################################
#
#  New implementation
#
###############################################################################

class PreCheckForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(PreCheckForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.IntegerField(widget=HiddenInput)

        self.fields['username'] = forms.CharField(
            label=_("User name"),
            required=False,
            max_length=OS_LNAME_LEN
        )

        curr_year = datetime.datetime.now().year            
        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            required=False,
            widget=SelectDateWidget(None, range(curr_year, curr_year + 25))
        )

    def _retrieve_email(self, request, uid):
        try:
            tmpusr = keystone_api.user_get(request, uid)
            return tmpusr.email
        except:
            LOG.error("Cannot retrieve email", exc_info=True)
        return None

    def _generate_pwd(self):
        if crypto_version.startswith('2.0'):
            prng = randpool.RandomPool()
            iv = prng.get_bytes(256)
        else:
            prng = Random.new()
            iv = prng.read(16)
        return base64.b64encode(iv)
    
    @sensitive_variables('data')
    def handle(self, request, data):

        if not data['username']:
            messages.error(request, _("Cannot process request: missing username"))
            return False
        if not data['expiration']:
            messages.error(request, _("Cannot process request: missing expiration date"))
            return False

        try:

            with transaction.atomic():

                registration = Registration.objects.get(regid=int(data['regid']))

                userReqList = RegRequest.objects.filter(registration=registration)
                if len(userReqList) == 0:
                    raise Exception("Cannot find registration request")
                    
                prjReqList = PrjRequest.objects.filter(registration=registration)

                #
                # User renaming (move down)
                #
                if registration.userid == None:
                
                    registration.username = data['username']
                    registration.expdate = data['expiration']
                    registration.save()

                #
                # Forward request to project administrators
                #
                q_args = {
                    'project__projectid__isnull' : False,
                    'flowstatus' : PSTATUS_REG
                }
                prjreq_new = prjReqList.filter(**q_args)
                prjreq_new.update(flowstatus=PSTATUS_PENDING)

                #
                # Send notifications to project administrators and users
                #
                for p_item in prjreq_new:
                
                    m_users = get_project_managers(request, p_item.project.projectid)
                    m_emails = [ usr.email for usr in m_users ]
                    
                    noti_params = {
                        'username' : registration.username,
                        'project' : p_item.project.projectname
                    }
                    noti_sbj, noti_body = notification_render(SUBSCR_WAIT_TYPE, noti_params)
                    notifyUsers(m_emails, noti_sbj, noti_body)
                    
                    if email:
                        n2_params = {
                            'project' : p_item.project.projectname,
                            'prjadmins' : m_emails
                        }
                        noti_sbj, noti_body = notification_render(SUBSCR_ONGOING, n2_params)
                        notifyUsers(email, noti_sbj, noti_body)

                #
                # Mapping of external accounts
                #                
                if userReqList[0].externalid:
                    LOG.debug("Registering external account %s" % userReqList[0].externalid)
                    mapping = UserMapping(globaluser=userReqList[0].externalid,
                                    registration=userReqList[0].registration)
                    mapping.save()
                    
                password = userReqList[0].password
                if not password:
                    password = self._generate_pwd()

                #
                # User creation
                #
                if not registration.userid:
                    
                    kuser = keystone_api.user_create(request, 
                                                    name=registration.username,
                                                    password=password,
                                                    email=userReqList[0].email,
                                                    enabled=True)
                        
                    registration.userid = kuser.id
                    registration.save()
                    first_registr = True

                #
                # cache cleanup
                #
                userReqList.delete()

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            messages.error(request, exc_value)
            return False

        return True

    
                










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
            all_prj_req = list()
            recipients = None
            first_reg_rej = False

            with transaction.atomic():
                
                registration = Registration.objects.get(regid=int(data['regid']))
                prjReqList = PrjRequest.objects.filter(registration=registration)
                regReqList = RegRequest.objects.filter(registration=registration)
                    
                #
                # Delete request for projects to be created
                #
                newprj_list = list()
                for prj_req in prjReqList:
                    all_prj_req.append(prj_req.project.projectname)
                    if not prj_req.project.projectid:
                        newprj_list.append(prj_req.project.projectname)
                    
                if len(newprj_list):
                    Project.objects.filter(projectname__in=newprj_list).delete()
                    
                if registration.userid:
                    #
                    # User already registered, remove just the pending requests
                    #
                    
                    prjReqList.delete()
                        
                    regReqList.delete()
                    
                    recipients = self._retrieve_email(request, registration.userid)
                        
                else:
                    #
                    # First registration request, remove all (via foreign key)
                    #
                
                    recipients = [ x for x in regReqList.values_list('email', flat=True) ]
                    
                    registration.delete()
                    first_reg_rej = True
            
            if first_reg_rej:
            
                noti_params = {
                    'notes' : data['reason']
                }
                noti_sbj, noti_body = notification_render(FIRST_REG_NO_TYPE, noti_params)
                notifyUsers(recipients, noti_sbj, noti_body)
            
            elif all_prj_req:
                noti_params = {
                    'projects_rejected' : all_prj_req
                }
                noti_sbj, noti_body = notification_render(SUBSCR_NO_TYPE, noti_params)
                notifyUsers(recipients, noti_sbj, noti_body)

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            messages.error(request, exc_value)
            return False

        return True


