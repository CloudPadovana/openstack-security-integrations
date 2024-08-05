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
from datetime import datetime, timedelta

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy as reverse
from django.db import transaction

from horizon import tables
from horizon import exceptions
from horizon import forms

from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import NEW_MODEL
if NEW_MODEL:
    from openstack_auth_shib.models import PrjAttribute

from openstack_auth_shib.models import RSTATUS_PENDING
from openstack_auth_shib.models import RSTATUS_REMINDACK
from openstack_auth_shib.models import PRJ_PRIVATE
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import PSTATUS_RENEW_ATTEMPT
from openstack_auth_shib.models import PSTATUS_RENEW_DISC
from openstack_auth_shib.models import PSTATUS_CHK_COMP
from openstack_auth_shib.utils import REQID_REGEX
from openstack_auth_shib.utils import unique_admin
from openstack_auth_shib.utils import getProjectInfo
from openstack_auth_shib.utils import ATT_PRJ_EXP

from .utils import RegistrData
from .tables import OperationTable
from .forms import PreCheckForm
from .forms import GrantAllForm
from .forms import RejectForm
from .forms import ForcedCheckForm
from .forms import ForcedRejectForm
from .forms import NewProjectCheckForm
from .forms import NewProjectRejectForm
from .forms import RenewAdminForm
from .forms import DetailsForm
from .forms import RemainderAckForm
from .forms import CompAckForm

LOG = logging.getLogger(__name__)

class MainView(tables.DataTableView):
    table_class = OperationTable
    template_name = 'idmanager/registration_manager/reg_manager.html'
    page_title = _("Registrations")

    def get_data(self):
    
        reqTable = dict()
        
        with transaction.atomic():
        
            regid_pending = set()
            for tmpRegReq in RegRequest.objects.filter(flowstatus=RSTATUS_PENDING):
                regid_pending.add(tmpRegReq.registration.regid)

            for tmpRegReq in RegRequest.objects.filter(flowstatus=RSTATUS_REMINDACK):
                req_id = "%d:" % tmpRegReq.registration.regid
                rData = RegistrData(
                    registration = tmpRegReq.registration,
                    requestid = req_id,
                    code = RegistrData.REMINDER
                )
                reqTable[req_id] = rData

            for prjReq in PrjRequest.objects.all():

                rData = RegistrData(registration = prjReq.registration)
                curr_regid = prjReq.registration.regid

                if prjReq.flowstatus >= PSTATUS_CHK_COMP:

                    rData.project = prjReq.project.projectname
                    rData.notes = prjReq.notes
                    requestid = "%d:%s" % (curr_regid, prjReq.project.projectname)
                    
                    if prjReq.flowstatus == PSTATUS_CHK_COMP:
                        rData.code = RegistrData.CHK_COMP
                    elif prjReq.flowstatus == PSTATUS_RENEW_ATTEMPT:
                        rData.code = RegistrData.REN_ATTEMPT
                    elif prjReq.flowstatus == PSTATUS_RENEW_DISC:
                        rData.code = RegistrData.REN_DISC
                    elif prjReq.flowstatus == PSTATUS_RENEW_MEMB:
                        rData.code = RegistrData.USR_RENEW
                    elif prjReq.flowstatus == PSTATUS_RENEW_ADMIN:
                        rData.code = RegistrData.PRJADM_RENEW
                        if unique_admin(prjReq.registration.username, prjReq.project.projectname):
                            rData.notes += " (%s)" % _("Unique administrator")

                elif prjReq.project.projectid:

                    if curr_regid in regid_pending:
                        rData.code = RegistrData.NEW_USR_EX_PRJ
                        requestid = "%d:" % curr_regid
                    else:
                        rData.code = RegistrData.EX_USR_EX_PRJ
                        rData.project = prjReq.project.projectname
                        requestid = "%d:%s" % (curr_regid, prjReq.project.projectname)

                else:

                    if curr_regid in regid_pending:
                        rData.code = RegistrData.NEW_USR_NEW_PRJ
                    else:
                        rData.code = RegistrData.EX_USR_NEW_PRJ
                    rData.project = prjReq.project.projectname
                    requestid = "%d:%s" % (curr_regid, prjReq.project.projectname)
                    if prjReq.project.status == PRJ_PRIVATE:
                        rData.project += " (%s)" % _("Private")

                rData.requestid = requestid
                
                if not requestid in reqTable:
                    reqTable[requestid] = rData

        result = list(reqTable.values())
        result.sort()
        return result

class AbstractCheckView(forms.ModalFormView):

    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                tmpm = REQID_REGEX.search(self.kwargs['requestid'])
                regid = int(tmpm.group(1))
                
                tmplist = RegRequest.objects.filter(registration__regid=regid, flowstatus=RSTATUS_PENDING)
                if len(tmplist):
                    self._object = tmplist[0]
                else:
                    raise Exception("Database error")
                    
            except Exception:
                LOG.error("Registration error", exc_info=True)
                redirect = reverse("horizon:idmanager:registration_manager:index")
                exceptions.handle(self.request, _('Unable to pre-check request.'), redirect=redirect)

        return self._object

    def get_context_data(self, **kwargs):
        context = super(AbstractCheckView, self).get_context_data(**kwargs)
        context['requestid'] = "%d:" % self.get_object().registration.regid
        context['extaccount'] = self.get_object().externalid
        context['contact'] = self.get_object().contactper
        context['organization'] = self.get_object().registration.organization
        context['email'] = self.get_object().email
        return context

class PreCheckView(AbstractCheckView):
    form_class = PreCheckForm
    template_name = 'idmanager/registration_manager/precheck.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_initial(self):
        return {
            'regid' : self.get_object().registration.regid,
            'username' : self.get_object().registration.username,
            'extaccount' : self.get_object().externalid
        }

class GrantAllView(AbstractCheckView):
    form_class = GrantAllForm
    template_name = 'idmanager/registration_manager/precheck.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_context_data(self, **kwargs):
        context = super(GrantAllView, self).get_context_data(**kwargs)
        context['grantallmode'] = True
        return context

    def get_initial(self):

        oldpname, oldpdescr, exp_d = get_project_details(self.kwargs.get('requestid', ''))

        return {
            'regid' : self.get_object().registration.regid,
            'username' : self.get_object().registration.username,
            'extaccount' : self.get_object().externalid,
            'expiration' : exp_d if exp_d else datetime.now() + timedelta(365),
            'rename' : oldpname if oldpname else '' ,
            'newdescr' : oldpdescr if oldpdescr else ''
        }

class RejectView(AbstractCheckView):
    form_class = RejectForm
    template_name = 'idmanager/registration_manager/reject.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_initial(self):
        return {
            'regid' : self.get_object().registration.regid
        }

class ForcedApproveView(forms.ModalFormView):
    form_class = ForcedCheckForm
    template_name = 'idmanager/registration_manager/forced.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

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
            'expiration' : datetime.now() + timedelta(365)
        }

class ForcedRejectView(forms.ModalFormView):
    form_class = ForcedRejectForm
    template_name = 'idmanager/registration_manager/forced.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

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
            'requestid' : self.kwargs['requestid']
        }

class NewProjectView(forms.ModalFormView):
    form_class = NewProjectCheckForm
    template_name = 'idmanager/registration_manager/newproject.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')
    
    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['requestid']
        return self._object

    def get_context_data(self, **kwargs):
        context = super(NewProjectView, self).get_context_data(**kwargs)
        context['requestid'] = self.kwargs['requestid']
        context['action'] = 'accept'
        return context
        
    def get_initial(self):

        oldpname, oldpdescr, exp_d = get_project_details(self.kwargs['requestid'])

        return { 
            'requestid' : self.kwargs['requestid'],
            'newname' : oldpname if oldpname else '',
            'newdescr' : oldpdescr if oldpdescr else '',
            'expiration' : exp_d if exp_d else datetime.now() + timedelta(365)
        }

class RejectProjectView(forms.ModalFormView):
    form_class = NewProjectRejectForm
    template_name = 'idmanager/registration_manager/newproject.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')
    
    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['requestid']
        return self._object

    def get_context_data(self, **kwargs):
        context = super(RejectProjectView, self).get_context_data(**kwargs)
        context['requestid'] = self.kwargs['requestid']
        context['action'] = 'reject'
        return context
        
    def get_initial(self):
        return { 
            'requestid' : self.kwargs['requestid']
        }

class RenewAdminView(forms.ModalFormView):
    form_class = RenewAdminForm
    template_name = 'idmanager/registration_manager/renewadmin.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['requestid']
        return self._object

    def get_context_data(self, **kwargs):
        context = super(RenewAdminView, self).get_context_data(**kwargs)
        context['requestid'] = self.kwargs['requestid']
        context['action'] = 'accept'
        context['is_admin'] = True
        return context
        
    def get_initial(self):
        return { 
            'requestid' : self.kwargs['requestid'],
            'expiration' : datetime.now() + timedelta(365)
        }

class ForcedRenewView(RenewAdminView):
    form_class = RenewAdminForm
    template_name = 'idmanager/registration_manager/renewadmin.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_context_data(self, **kwargs):
        context = super(ForcedRenewView, self).get_context_data(**kwargs)
        context['is_admin'] = False
        return context

class DetailsView(forms.ModalFormView):
    form_class = DetailsForm
    template_name = 'idmanager/registration_manager/details.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                tmpm = REQID_REGEX.search(self.kwargs['requestid'])
                regid = int(tmpm.group(1))
                prjname = tmpm.group(2) if tmpm.group(2) else None

                tmpdict = dict()
                tmpdict['requestid'] = self.kwargs['requestid']
                tmpdict['regid'] = regid
                tmpdict['newprojects'] = list()
                tmpdict['memberof'] = list()
                reg_item = None
                prj_list = list()

                tmpres = RegRequest.objects.filter(registration__regid=regid)
                if len(tmpres):
                    reg_item = tmpres[0].registration
                    tmpdict['extaccount'] = tmpres[0].externalid
                    tmpdict['contact'] = tmpres[0].contactper
                    tmpdict['email'] = tmpres[0].email
                    tmpdict['notes'] = tmpres[0].notes

                    if tmpres[0].flowstatus == RSTATUS_PENDING:
                        for x in PrjRequest.objects.filter(registration__regid=regid):
                            prj_list.append(x.project)
                    else:
                        for x in Expiration.objects.filter(registration__regid=regid):
                            prj_list.append(x.project)

                elif prjname:
                    q_args = {
                        'registration__regid' : regid,
                        'project__projectname' : prjname
                    }
                    prj_req = PrjRequest.objects.filter(**q_args)[0]
                    reg_item = prj_req.registration
                    prj_list.append(prj_req.project)

                    tmpem = EMail.objects.filter(registration__regid=regid)
                    tmpdict['email'] = tmpem[0].email if len(tmpem) else "-"
                    tmpdict['notes'] = prj_req.notes
                    tmpctc = self._getContact(reg_item.organization)
                    if tmpctc:
                        tmpdict['contact'] = tmpctc

                if reg_item:
                    tmpdict['username'] = reg_item.username
                    tmpdict['fullname'] = reg_item.givenname + " " + reg_item.sn
                    tmpdict['organization'] = reg_item.organization
                    tmpdict['phone'] = reg_item.phone

                for prj_item in prj_list:
                    if prj_item.projectid:
                        tmpdict['memberof'].append(getProjectInfo(self.request, prj_item))
                    else:
                        is_priv = prj_item.status == PRJ_PRIVATE
                        tmpt = (prj_item.projectname, prj_item.description, is_priv)
                        tmpdict['newprojects'].append(tmpt)

                self._object = tmpdict

            except Exception:
                LOG.error("Registration error", exc_info=True)
                redirect = reverse("horizon:idmanager:registration_manager:index")
                exceptions.handle(self.request, _('Unable to retrieve details.'), redirect=redirect)

        return self._object

    def get_initial(self):
        return { 'requestid' : self.kwargs['requestid'] }

    def get_context_data(self, **kwargs):
        context = super(DetailsView, self).get_context_data(**kwargs)
        context.update(self.get_object())
        return context

    def _getContact(self, dept_id):
        for o_name, o_data in settings.HORIZON_CONFIG.get('organization', {}).items():
            for ou_tuple in o_data:
                if len(ou_tuple) > 4 and ou_tuple[0] == dept_id:
                    return "%s <%s> (tel: %s)" % ou_tuple[2:]
        return None


class RemainderAckView(forms.ModalFormView):
    form_class = RemainderAckForm
    template_name = 'idmanager/registration_manager/generic_ack.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['requestid']
        return self._object

    def get_initial(self):
        return { 'requestid' : self.kwargs['requestid'] }

    def get_context_data(self, **kwargs):
        context = super(RemainderAckView, self).get_context_data(**kwargs)
        context['form_action'] = reverse("horizon:idmanager:registration_manager:remainderack",
                                         args=(self.get_object(),))
        context['op_question'] = _('Do you confirm that the enrollment is completed?')
        return context

class CompAckView(forms.ModalFormView):
    form_class = CompAckForm
    template_name = 'idmanager/registration_manager/generic_ack.html'
    success_url = reverse('horizon:idmanager:registration_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = self.kwargs['requestid']
        return self._object

    def get_initial(self):
        return { 'requestid' : self.kwargs['requestid'] }

    def get_context_data(self, **kwargs):
        context = super(CompAckView, self).get_context_data(**kwargs)
        context['form_action'] = reverse("horizon:idmanager:registration_manager:compack",
                                         args=(self.get_object(),))
        context['op_question'] = _('Do you confirm that the compliance check is fine?')
        return context

def get_project_details(requestid):

    #
    # TODO investigate: called twice
    #
    tmpm = REQID_REGEX.search(requestid)

    if tmpm and tmpm.group(2):

        with transaction.atomic():
            try:
                prj_obj = PrjRequest.objects.filter(
                    registration__regid = int(tmpm.group(1)),
                    project__projectname = tmpm.group(2)
                )[0].project

                prj_exp = None
                if NEW_MODEL:
                    exp_items = PrjAttribute.objects.filter(
                        project = prj_obj,
                        name = ATT_PRJ_EXP
                    )
                    if len(exp_items):
                        prj_exp = exp_items[0].value

                return (prj_obj.projectname, prj_obj.description, prj_exp)
            except Exception:
                LOG.error("Registration error", exc_info=True)

    return (None, None, None)



