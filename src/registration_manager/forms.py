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

import notifications

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

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)
TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')

def managersForPrj(request, prjId):
    result = list()

    #
    # TODO verify number of calls to keystone
    #
    for user in  keystone_api.user_list(request, project=prjId):
        for role in keystone_api.roles_for_user(request,user.id, prjId):
            if role.name == TENANTADMIN_ROLE:
                result.append(user)

    return result

class ProcessRegForm(forms.SelfHandlingForm):

    checkaction = forms.CharField(widget=HiddenInput, initial='accept')
    
    def __init__(self, request, *args, **kwargs):
        super(ProcessRegForm, self).__init__(request, *args, **kwargs)
        
        self.fields['regid'] = forms.IntegerField(widget=HiddenInput)
        self.fields['processinglevel'] = forms.IntegerField(widget=HiddenInput)
        self.prjman_roleid = None
        
        flowstatus = kwargs['initial']['processinglevel']
        if flowstatus == RSTATUS_PENDING or flowstatus == RSTATUS_NOFLOW:
            self.fields['username'] = forms.CharField(
                label=_("User name"),
                max_length=OS_LNAME_LEN
            )
                
            self.fields['expiration'] = forms.DateTimeField(
                label=_("Expiration date"),
                initial=datetime.datetime.now() + datetime.timedelta(365),
                widget=SelectDateWidget
            )
        else:
            self.fields['username'] = forms.CharField(
                label=_("User name"),
                widget = forms.TextInput(attrs={'readonly': 'readonly'})
            )
            
        if flowstatus == RSTATUS_CHECKED or flowstatus == RSTATUS_NOFLOW:
            self.fields['role_id'] = forms.ChoiceField(label=_("Role"))
            
            role_list = list()
            for role in keystone_api.role_list(request):
                if role.name == TENANTADMIN_ROLE:
                    self.prjman_roleid = role.id
                else:
                    role_list.append((role.id, role.name))
                
            #
            # Creation of project-manager role if necessary
            #
            if not self.prjman_roleid:
                self.prjman_roleid = keystone_api.role_create(request, TENANTADMIN_ROLE)
            role_list.append((self.prjman_roleid, TENANTADMIN_ROLE))
            
            self.fields['role_id'].choices = role_list

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
            return [ tmpusr.email ]
        except:
            LOG.error("Cannot retrieve email", exc_info=True)
        return []

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
    
        with transaction.commit_on_success():
            
            registration = Registration.objects.get(regid=int(data['regid']))
            flowstatus = int(data['processinglevel'])
            
            userReqList = RegRequest.objects.filter(registration=registration)
                
            prjReqList = PrjRequest.objects.filter(registration=registration)
                
            if flowstatus == RSTATUS_PENDING or flowstatus == RSTATUS_NOFLOW:
                #
                # User renaming
                #
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
                
                    m_users = managersForPrj(request, p_item.project.projectid)
                    
                    msg_obj = notifications.PrjManagerMessage(
                        username=registration.username,
                        projectname=p_item.project.projectname
                    )
                    notifications.notify([ usr.email for usr in m_users ], msg_obj)
                    
            if flowstatus == RSTATUS_CHECKED or flowstatus == RSTATUS_NOFLOW:
                main_tenant = None
                email = None
                password = None
                
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
                        
                    if not email:
                        email = tmpReq.email
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
                    
                else:
                    email = self._retrieve_email(request, registration.userid)
                
                for prj_req in prjs_approved:
                    keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, data['role_id'])
                    
                for prj_req in prjs_to_create:
                    keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, data['role_id'])

                    if self.prjman_roleid and self.prjman_roleid <> data['role_id']:
                        keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, self.prjman_roleid)
                
                
                notifications.notify(email, notifications.TenantNotifMessage(
                    username = registration.username,
                    prj_ok = [ prj_req.project.projectname for prj_req in prjs_approved ],
                    prj_no = [ prj_req.project.projectname for prj_req in prjs_rejected ],
                    prj_new = [ prj_req.project.projectname for prj_req in prjs_to_create ]
                ))
                
                
                #
                # cache cleanup
                #
                prjReqList.delete()
                userReqList.delete()
                
    def _handle_reject(self, request, data):
            
        all_prj_req = list()
        recipients = None
        first_reg_rej = False

        with transaction.commit_on_success():
            
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
        
            notifications.notify(recipients, notifications.REGISTRATION_NOT_AUTHORIZED)
        
        elif all_prj_req:
            msg_obj = notifications.TenantNotifMessage(prj_no = all_prj_req)
            notifications.notify(recipients, msg_obj)


