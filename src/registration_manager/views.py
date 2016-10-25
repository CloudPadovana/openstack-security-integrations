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

import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.db import transaction
from django.db.models import Q

from horizon import tables
from horizon import exceptions
from horizon import forms

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PRJ_GUEST

from openstack_auth_shib.models import PSTATUS_APPR
from openstack_auth_shib.models import PSTATUS_REJ
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_REG

from openstack_auth_shib.models import RSTATUS_PENDING
from openstack_auth_shib.models import RSTATUS_PRECHKD
from openstack_auth_shib.models import RSTATUS_CHECKED
from openstack_auth_shib.models import RSTATUS_NOFLOW

from .tables import RegisterTable, OperationTable
from .forms import ProcessRegForm, ForceApproveForm

LOG = logging.getLogger(__name__)


class IndexView(tables.DataTableView):
    table_class = RegisterTable
    template_name = 'idmanager/registration_manager/reg_manager.html'

    def get_data(self):
    
        query1 = Q(regid__in=RegRequest.objects.all().values_list('registration'))
        query2 = Q(regid__in=PrjRequest.objects.all().values_list('registration'))
        
        #
        # TODO paging
        #
        return Registration.objects.filter(query1 | query2).order_by('username')


class PrjInfo:
    def __init__(self, name, status):
        self.name = name
        self.visible = status
    
    def __str__(self):
        return self.name

class RegReqItem:
    
    def __init__(self, regid):
    
        registration = Registration.objects.get(regid=regid)
        
        self.regid = regid
        self.username = registration.username
        self.reqlevel = RSTATUS_CHECKED
        self.extaccounts = list()
        self.regprojects = list()
        self.pendprojects = list()
        self.apprprojects = list()
        self.rejprojects = list()
        self.newprojects = list()
        self.contacts = list()
        self.emails = list()
        
        regreq_list = RegRequest.objects.filter(registration=registration)
        if len(regreq_list):
            for reg_req in regreq_list:
                if reg_req.externalid:
                    self.extaccounts.append(reg_req.externalid)
                self.reqlevel = min(self.reqlevel, reg_req.flowstatus)
                self.contacts.append(reg_req.contactper)
                self.emails.append(reg_req.email)
        else:
            self.reqlevel = RSTATUS_PRECHKD

        prj_mark = True
        found_guest = False
        prjreq_list = PrjRequest.objects.filter(registration=registration)
        for prj_req in prjreq_list:
            if prj_req.project.projectid:
            
                if prj_req.flowstatus == PSTATUS_REG:
                    prj_mark = False
                if prj_req.project.status == PRJ_GUEST:
                    found_guest = True
                
                if prj_req.flowstatus == PSTATUS_REG:
                    self.regprojects.append(prj_req.project.projectname)
                elif prj_req.flowstatus == PSTATUS_PENDING:
                    self.pendprojects.append(prj_req.project.projectname)
                elif prj_req.flowstatus == PSTATUS_APPR:
                    self.apprprojects.append(prj_req.project.projectname)
                else:
                    self.rejprojects.append(prj_req.project.projectname)
                
            else:
                tmpp = PrjInfo(prj_req.project.projectname, prj_req.project.status)
                self.newprojects.append(tmpp)
                
        if prj_mark and self.reqlevel == RSTATUS_PRECHKD:
            self.reqlevel = RSTATUS_CHECKED
        
        if self.reqlevel == RSTATUS_PENDING and len(self.newprojects) \
            and len(self.regprojects) == 0 and len(self.pendprojects) == 0 \
            and len(self.apprprojects) == 0 and len(self.rejprojects) == 0:
            self.reqlevel = RSTATUS_NOFLOW

        if self.reqlevel == RSTATUS_PENDING and len(self.newprojects) == 0 \
            and (len(self.regprojects) + len(self.pendprojects) \
                 + len(self.apprprojects) + len(self.rejprojects)) == 1 \
            and found_guest:
            self.reqlevel = RSTATUS_NOFLOW

class ProcessView(forms.ModalFormView):
    form_class = ProcessRegForm
    template_name = 'idmanager/registration_manager/reg_process.html'
    success_url = reverse_lazy('horizon:idmanager:registration_manager:index')
    
    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                self._object = RegReqItem(int(self.kwargs['regid']))
            except Exception:
                LOG.error("Registration error", exc_info=True)
                redirect = reverse_lazy("horizon:idmanager:registration_manager:index")
                exceptions.handle(self.request, _('Unable approve registration.'),
                                  redirect=redirect)
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ProcessView, self).get_context_data(**kwargs)
        context['regid'] = self.get_object().regid
        context['username'] = self.get_object().username
        context['extaccounts'] = self.get_object().extaccounts
        context['processinglevel'] = self.get_object().reqlevel
        context['newprojects'] = self.get_object().newprojects
        context['regprojects'] = self.get_object().regprojects
        context['pendprojects'] = self.get_object().pendprojects
        context['apprprojects'] = self.get_object().apprprojects
        context['rejprojects'] = self.get_object().rejprojects
        context['contacts'] = self.get_object().contacts
        context['emails'] = self.get_object().emails

        context['approveenabled'] = True
        if self.get_object().reqlevel == RSTATUS_PENDING:
            context['processingtitle'] = _('Pre-check registrations')
            context['processingbtn'] = _('Pre-check')
        elif self.get_object().reqlevel == RSTATUS_PRECHKD:
            context['processingtitle'] = _('Pre-check project subscriptions')
            context['processingbtn'] = _('Pre-check')
        else:
            context['processingtitle'] = _('Approve registrations')
            context['processingbtn'] = _('Approve')
            
            tmpsum = len(self.get_object().regprojects)
            tmpsum += len(self.get_object().apprprojects)
            tmpsum += len(self.get_object().newprojects)
            
            if len(self.get_object().pendprojects) > 0:
                context['approveenabled'] = False
                
            if len(self.get_object().rejprojects) > 0 and tmpsum == 0:
                context['approveenabled'] = False

        return context

    def get_initial(self):
        return {
            'regid' : self.get_object().regid,
            'username' : self.get_object().username,
            'processinglevel' : self.get_object().reqlevel
        }

class ForceApprView(forms.ModalFormView):
    form_class = ForceApproveForm
    template_name = 'idmanager/registration_manager/reg_approve.html'
    
    def get_success_url(self):
        return reverse_lazy('horizon:idmanager:registration_manager:process',
                            kwargs=self.kwargs)
        
    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['regid']
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ForceApprView, self).get_context_data(**kwargs)
        context['regid'] = self.kwargs['regid']
        return context
        
    def get_initial(self):
        return { 'regid' : self.kwargs['regid'] }

###############################################################################
#
#  New implementation
#
###############################################################################
import datetime

from .tables import RegistrData
from .forms import PreCheckForm, RejectForm, ForcedCheckForm

class MainView(tables.DataTableView):
    table_class = OperationTable
    template_name = 'idmanager/registration_manager/reg_manager.html'

    def get_data(self):
    
        reqTable = dict()
        
        with transaction.atomic():
        
            allPrjReqs = PrjRequest.objects.all()
            
            allRegReqs = RegRequest.objects.filter(flowstatus=RSTATUS_PENDING)
            
            regid_list = [ tmpRegReq.registration.regid for tmpRegReq in allRegReqs ]
            
            for prjReq in allPrjReqs:
                
                rData = RegistrData()
                rData.username = prjReq.registration.username
                rData.fullname = prjReq.registration.givenname + " " + prjReq.registration.sn
                rData.organization = prjReq.registration.organization
                rData.phone = prjReq.registration.phone
                
                if prjReq.project.projectid:
                    if prjReq.registration.regid in regid_list:
                        rData.code = RegistrData.NEW_USR_EX_PRJ
                        requestid = "%d:" % prjReq.registration.regid
                    else:
                        rData.code = RegistrData.EX_USR_EX_PRJ
                        rData.project = prjReq.project.projectname
                        requestid = "%d:%s" % (prjReq.registration.regid, prjReq.project.projectname)
                else:
                    if prjReq.registration.regid in regid_list:
                        rData.code = RegistrData.NEW_USR_NEW_PRJ
                        rData.project = prjReq.project.projectname
                        requestid = "%d:%s" % (prjReq.registration.regid, prjReq.project.projectname)
                    else:
                        rData.code = RegistrData.EX_USR_NEW_PRJ
                        rData.project = prjReq.project.projectname
                        requestid = "%d:%s" % (prjReq.registration.regid, prjReq.project.projectname)

                rData.requestid = requestid
                
                if not requestid in reqTable:
                    reqTable[requestid] = rData

        result = reqTable.values()
        result.sort()
        return result



class PreCheckView(forms.ModalFormView):
    form_class = PreCheckForm
    template_name = 'idmanager/registration_manager/precheck.html'
    success_url = reverse_lazy('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                tmpTuple = self.kwargs['requestid'].split(':')
                regid = int(tmpTuple[0])
                
                tmplist = RegRequest.objects.filter(registration__regid=regid)
                if len(tmplist):
                    self._object = tmplist[0]
                else:
                    raise Exception("Database error")
                    
            except Exception:
                LOG.error("Registration error", exc_info=True)
                redirect = reverse_lazy("horizon:idmanager:registration_manager:index")
                exceptions.handle(self.request, _('Unable to pre-check request.'), redirect=redirect)

        return self._object


    def get_context_data(self, **kwargs):
        context = super(PreCheckView, self).get_context_data(**kwargs)
        context['requestid'] = "%d:" % self.get_object().registration.regid
        context['extaccount'] = self.get_object().externalid
        context['contact'] = self.get_object().contactper
        context['email'] = self.get_object().email
        return context

    def get_initial(self):
        return {
            'regid' : self.get_object().registration.regid,
            'username' : self.get_object().registration.username,
            'expiration' : datetime.datetime.now() + datetime.timedelta(365)
        }


class RejectView(forms.ModalFormView):
    form_class = RejectForm
    template_name = 'idmanager/registration_manager/reject.html'
    success_url = reverse_lazy('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                tmpTuple = self.kwargs['requestid'].split(':')
                regid = int(tmpTuple[0])
                
                tmplist = RegRequest.objects.filter(registration__regid=regid)
                if len(tmplist):
                    self._object = tmplist[0]
                else:
                    raise Exception("Database error")
                    
            except Exception:
                LOG.error("Registration error", exc_info=True)
                redirect = reverse_lazy("horizon:idmanager:registration_manager:index")
                exceptions.handle(self.request, _('Unable to pre-check request.'), redirect=redirect)

        return self._object


    def get_context_data(self, **kwargs):
        context = super(RejectView, self).get_context_data(**kwargs)
        context['requestid'] = "%d:" % self.get_object().registration.regid
        context['extaccount'] = self.get_object().externalid
        context['contact'] = self.get_object().contactper
        context['email'] = self.get_object().email
        return context

    def get_initial(self):
        return {
            'regid' : self.get_object().registration.regid
        }

class ForcedApproveView(forms.ModalFormView):
    form_class = ForcedCheckForm
    template_name = 'idmanager/registration_manager/forced.html'
    success_url = reverse_lazy('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['requestid']
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ForcedApproveView, self).get_context_data(**kwargs)
        context['requestid'] = self.kwargs['requestid']
        context['action'] = 'accept'
        return context
        
    def get_initial(self):
        return { 
            'requestid' : self.kwargs['requestid'],
            'action' : 'accept'
        }

class ForcedRejectView(forms.ModalFormView):
    form_class = ForcedCheckForm
    template_name = 'idmanager/registration_manager/forced.html'
    success_url = reverse_lazy('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['requestid']
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ForcedRejectView, self).get_context_data(**kwargs)
        context['requestid'] = self.kwargs['requestid']
        context['action'] = 'reject'
        return context
        
    def get_initial(self):
        return { 
            'requestid' : self.kwargs['requestid'],
            'action' : 'reject'
        }

