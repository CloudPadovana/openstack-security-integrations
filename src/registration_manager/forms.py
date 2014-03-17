import logging
import base64
from Crypto import __version__ as crypto_version
if crypto_version.startswith('2.0'):
    from Crypto.Util import randpool
else:
    from Crypto import Random

from horizon import forms
from horizon import exceptions

from django.db import transaction
from django.forms.widgets import HiddenInput
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

from openstack_auth_shib.models import TENANTADMIN_ROLE

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)

class ProcessRegForm(forms.SelfHandlingForm):

    checkaction = forms.CharField(widget=HiddenInput, initial='accept')
    
    def __init__(self, request, *args, **kwargs):
        super(ProcessRegForm, self).__init__(request, *args, **kwargs)
        
        self.fields['regid'] = forms.IntegerField(widget=HiddenInput)
        self.fields['processinglevel'] = forms.IntegerField(widget=HiddenInput)
        self.prjman_roleid = None
        
        flowstatus = kwargs['initial']['processinglevel']
        if flowstatus == RSTATUS_PENDING:
            self.fields['username'] = forms.CharField(label=_("User name"))
        else:
            self.fields['username'] = forms.CharField(label=_("User name"),
                widget = forms.TextInput(attrs={'readonly': 'readonly'}))
            
            if flowstatus == RSTATUS_CHECKED:
                self.fields['role_id'] = forms.ChoiceField(label=_("Role"))
            
                role_list = list()
                for role in keystone_api.role_list(request):
                    if role.name == TENANTADMIN_ROLE:
                        self.prjman_roleid = role.id
                    role_list.append((role.id, role.name))
            
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

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
            if data['checkaction'] == 'accept':
                self._handle_accept(request, data)
            else:
                self._handle_reject(request, data)
        except:
            exceptions.handle(request, _("No tenants for first registration"))
            return False

        return True



    def _handle_accept(self, request, data):
    
        with transaction.commit_on_success():
            
            registration = Registration.objects.get(regid=int(data['regid']))
            flowstatus = int(data['processinglevel'])
            
            userReqList = RegRequest.objects.filter(registration=registration)
                
            prjReqList = PrjRequest.objects.filter(registration=registration)
                
            if flowstatus == RSTATUS_PENDING:
                #
                # User renaming
                #
                registration.username = data['username']
                registration.save()
                
            if flowstatus == RSTATUS_PENDING or flowstatus == RSTATUS_PRECHKD:
                #
                # Send request to prj-admin
                #
                q_args = {
                    'project__projectid__isnull' : False,
                    'flowstatus' : PSTATUS_REG
                }
                prjReqList.filter(**q_args).update(flowstatus=PSTATUS_PENDING)
                    
                userReqList.update(flowstatus=RSTATUS_CHECKED)
                    
            if flowstatus == RSTATUS_CHECKED:
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
                        raise exceptions.HorizonException(_("Cannot process request"))
                    
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
                        raise exceptions.HorizonException(_("No tenants for first registration"))
                        
                    if not email:
                        raise exceptions.HorizonException( _("No email for first registration"))
                        
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
                        
                
                for prj_req in prjs_approved:
                    keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, data['role_id'])
                    
                for prj_req in prjs_to_create:
                    keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, data['role_id'])

                    if self.prjman_roleid and self.prjman_roleid <> data['role_id']:
                        keystone_api.add_tenant_user_role(request, prj_req.project.projectid,
                                                    registration.userid, self.prjman_roleid)
                for prj_req in prjs_rejected:
                    LOG.debug("Reject membership request for %s to %s" \
                                    % (prj_req.project.projectname, registration.username))
                    
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
                
                try:
                    tmpusr = keystone_api.user_get(request, registration.userid)
                    recipients = [ tmpusr.email ]
                except:
                    LOG.error("Cannot retrieve email", exc_info=True)
                    
            else:
            
                recipients = [ x for x in regReqList.values_list('email', flat=True) ]
                
                registration.delete()
                first_reg_rej = True
        
        if first_reg_rej:
        
            notifications.notify(recipients, notifications.REGISTRATION_NOT_AUTHORIZED)
        
        elif all_prj_req.append:
            msg_obj = notifications.TenantNotifMessage(
                prj_no = [ prj_req.project.projectname for prj_req in all_prj_req.append ]
            )
            notifications.notify(recipients, msg_obj)


