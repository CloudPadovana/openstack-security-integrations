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
from django.utils.translation import ugettext_lazy as _

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
from openstack_auth_shib.models import RSTATUS_CHECKED

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)

class ProcessRegForm(forms.SelfHandlingForm):

    regid = forms.IntegerField(widget=HiddenInput)
    username = forms.CharField(label=_("User name"))
    role_id = forms.ChoiceField(label=_("Role"))
    #
    # TODO use a button instead of choice field
    #
    checkaction = forms.ChoiceField(label=_("Action"),
        choices=[
            ('accept', _('Accept')),
            ('reject', _('Reject'))
        ]
    )
    
    def __init__(self, request, *args, **kwargs):
        super(ProcessRegForm, self).__init__(request, *args, **kwargs)
        
        role_list = keystone_api.role_list(request)
        self.fields['role_id'].choices = [(role.id, role.name) for role in role_list]

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
    
        if data['checkaction'] == 'accept':
        
            with transaction.commit_on_success():
            
                registration = Registration.objects.get(regid=int(data['regid']))
                flowstatus = RSTATUS_CHECKED
            
                userReqList = RegRequest.objects.filter(registration=registration)
                for tmpReq in userReqList:
                    flowstatus = min(flowstatus, tmpReq.flowstatus)
                
                prjReqList = PrjRequest.objects.filter(registration=registration)
                
                if flowstatus == RSTATUS_PENDING:
                    #
                    # User renaming
                    #
                    registration.username = data['username']
                    registration.save()
                
                    #
                    # Send request to prj-admin
                    #
                    q_args = {
                        'project__projectid__isnull' : False,
                        'flowstatus' : PSTATUS_REG
                    }
                    prjReqList.filter(**q_args).update(flowstatus=PSTATUS_PENDING)
                    
                    userReqList.update(flowstatus=RSTATUS_CHECKED)
                    
                else:
                    main_tenant = None
                    email = None
                    password = None
                
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
                    for prj_req in prjReqList:
                    
                        if not prj_req.project.projectid:
                        
                            LOG.debug("Creating tenant %s" % prj_req.project.projectname)
                            kprj = keystone_api.tenant_create(request,
                                prj_req.project.projectname,
                                prj_req.project.description, True,
                                prj_req.registration.domain)
                            
                            prj_req.project.projectid = kprj.id
                            prj_req.project.save()
                            
                            prj_req.flowstatus = PSTATUS_APPR
                            prj_req.save()
                            
                        elif prj_req.flowstatus <= PSTATUS_PENDING:
                            exceptions.handle(request, _("Cannot process request"))
                            return False
                    
                        if not main_tenant:
                            main_tenant = prj_req.project
                    
                    #
                    # User creation
                    #
                    if not registration.userid:
                    
                        if not main_tenant:
                            exceptions.handle(request, _("No tenants for first registration"))
                            return False
                        
                        if not email:
                            exceptions.handle(request, _("No email for first registration"))
                            return False
                        
                        if not password:
                            password = self._generate_pwd()
                        
                        kuser = keystone_api.user_create(request, 
                                                    name=registration.username,
                                                    password=password,
                                                    email=email,
                                                    project=main_tenant.projectid,
                                                    enabled=True,
                                                    domain=registration.domain)
                        
                        registration.userid = kuser.id
                        registration.save()
                        
                        #
                        # TODO role project_manager for private tenants
                        #
                        for prj_req in prjReqList:
                            if prj_req.flowstatus == PSTATUS_APPR:
                                keystone_api.add_tenant_user_role(request,
                                                    prj_req.project.projectid,
                                                    kuser.id,
                                                    data['role_id'])
                            else:
                                LOG.debug("Reject membership request for %s to %s" \
                                    % (prj_req.project.projectname, registration.username))
                    
                    #
                    # cache cleanup
                    #
                    prjReqList.delete()
                    userReqList.delete()
                
        else:
            
            with transaction.commit_on_success():
            
                registration = Registration.objects.get(regid=int(data['regid']))
                prjReqList = PrjRequest.objects.filter(registration=registration)
                
                #
                # Delete projects to be created
                #
                newprj_list = list()
                for prj_req in prjReqList:
                    if not prj_req.project.projectid:
                        newprj_list.append(prj_req.project.projectname)
                
                if len(newprj_list):
                    Project.objects.filter(projectname__in=newprj_list).delete()
                
                if registration.userid:
                
                    prjReqList.delete()
                    
                    RegRequest.objects.filter(registration=registration).delete()
                    
                else:
                    registration.delete()
        
        return True




