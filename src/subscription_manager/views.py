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
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy

from horizon import tables
from horizon import messages
from horizon import forms

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB

from .tables import SubscriptionTable
from .forms import ApproveSubscrForm
from .forms import RejectSubscrForm
from .forms import RenewSubscrForm
from .forms import DiscSubscrForm

LOG = logging.getLogger(__name__)

class PrjReqItem:
    def __init__(self, prjReq):
        self.regid = prjReq.registration.regid
        self.username = prjReq.registration.username
        self.userid = prjReq.registration.userid
        self.fullname = prjReq.registration.givenname + " " + prjReq.registration.sn
        self.notes = prjReq.notes
        self.status = prjReq.flowstatus
    

class IndexView(tables.DataTableView):
    table_class = SubscriptionTable
    template_name = 'idmanager/subscription_manager/subscr_manager.html'

    def get_data(self):
    
        reqList = list()
        
        try:
            curr_prjname = self.request.user.tenant_name
            q_args = {
                'project__projectname' : curr_prjname,
                'flowstatus__in' : [ PSTATUS_PENDING, PSTATUS_RENEW_MEMB ]
            }
            for p_entry in PrjRequest.objects.filter(**q_args):
                reqList.append(PrjReqItem(p_entry))
            
        except Exception:
            LOG.error("Cannot retrieve list", exc_info=True)
            messages.error(self.request, _('Unable to retrieve subscription list.'))

        return reqList


class AbstractProcessView(forms.ModalFormView):
    
    def get_object(self):
        if not hasattr(self, "_object"):
            try:

                regid = int(self.kwargs['regid'])
                curr_prjname = self.request.user.tenant_name
                q_args = {
                    'project__projectname' : curr_prjname,
                    'registration__regid' : regid
                }
                self._object = PrjReqItem(PrjRequest.objects.filter(**q_args)[0])
                
            except Exception:
                LOG.error("Subscription error", exc_info=True)
                self._object = None

        return self._object

    def get_context_data(self, **kwargs):
        context = super(AbstractProcessView, self).get_context_data(**kwargs)
        context['regid'] = int(self.kwargs['regid'])

        if not self.get_object():
            context['subscr_err'] = _("Cannot retrieve user's data from database.")
            context['contacts'] = settings.MANAGERS
        else:
            context['username'] = self.get_object().username
            context['fullname'] = self.get_object().fullname
            context['notes'] = self.get_object().notes
            
        return context

    def get_initial(self):
    
        if not self.get_object():
            return dict()
            
        return {
            'regid' : self.get_object().regid,
        }

class ApproveView(AbstractProcessView):
    form_class = ApproveSubscrForm
    template_name = 'idmanager/subscription_manager/subscr_approve.html'
    success_url = reverse_lazy('horizon:idmanager:subscription_manager:index')

    def get_context_data(self, **kwargs):
        context = super(ApproveView, self).get_context_data(**kwargs)
        context['action'] = 'accept'
        return context

    def get_initial(self):
        inidata = super(ApproveView, self).get_initial()
        inidata['expiration'] = datetime.now() + timedelta(365)
        return inidata

class RejectView(AbstractProcessView):
    form_class = RejectSubscrForm
    template_name = 'idmanager/subscription_manager/subscr_approve.html'
    success_url = reverse_lazy('horizon:idmanager:subscription_manager:index')

    def get_context_data(self, **kwargs):
        context = super(RejectView, self).get_context_data(**kwargs)
        context['action'] = 'reject'
        return context

class RenewView(AbstractProcessView):
    form_class = RenewSubscrForm
    template_name = 'idmanager/subscription_manager/subscr_renew.html'
    success_url = reverse_lazy('horizon:idmanager:subscription_manager:index')

    def get_context_data(self, **kwargs):
        context = super(RenewView, self).get_context_data(**kwargs)
        context['action'] = 'accept'
        return context

    def get_initial(self):
        inidata = super(RenewView, self).get_initial()
        inidata['expiration'] = datetime.now() + timedelta(365)
        return inidata

class DiscardView(AbstractProcessView):
    form_class = DiscSubscrForm
    template_name = 'idmanager/subscription_manager/subscr_renew.html'
    success_url = reverse_lazy('horizon:idmanager:subscription_manager:index')

    def get_context_data(self, **kwargs):
        context = super(DiscardView, self).get_context_data(**kwargs)
        context['action'] = 'reject'
        return context

