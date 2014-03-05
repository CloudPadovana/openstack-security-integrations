import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy

from horizon import tables
from horizon import exceptions
from horizon import forms
from horizon import workflows

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PSTATUS_APPR
from openstack_auth_shib.models import PSTATUS_REJ
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_REG

from openstack_auth_shib.models import RSTATUS_PENDING
from openstack_auth_shib.models import RSTATUS_CHECKED

from .tables import RegisterTable
from .forms import ProcessRegForm
from .workflows import ApproveRegWorkflow

LOG = logging.getLogger(__name__)


class IndexView(tables.DataTableView):
    table_class = RegisterTable
    template_name = 'admin/registration_manager/reg_manager.html'

    def get_data(self):
    
        reqTable = dict()
        
        try:
            #
            # TODO paging
            #
            for r_entry in RegRequest.objects.all():
                reqTable[r_entry.registration.regid] = r_entry.registration
            
            for p_entry in PrjRequest.objects.all():
                if not p_entry.registration.regid in reqTable:
                    reqTable[p_entry.registration.regid] = p_entry.registration
            
        except Exception:
            exceptions.handle(self.request, _('Unable to retrieve registration list.'))

        return reqTable.values()




class ProcessView(forms.ModalFormView):
    form_class = ProcessRegForm
    template_name = 'admin/registration_manager/reg_process.html'
    success_url = reverse_lazy('horizon:admin:registration_manager:index')
    
    def get_object(self):
        registration = Registration.objects.get(regid=int(self.kwargs['regid']))
        return registration

    def get_context_data(self, **kwargs):
        context = super(ProcessView, self).get_context_data(**kwargs)
        context['regid'] = self.get_object().regid
        context['username'] = self.get_object().username
        
        context['extaccounts'] = list()
        context['processinglevel'] = RSTATUS_CHECKED
        regreq_list = RegRequest.objects.filter(registration=self.get_object())

        for reg_req in regreq_list:
            if reg_req.externalid:
                context['extaccounts'].append(reg_req.externalid)
            context['processinglevel'] = min(context['processinglevel'], reg_req.flowstatus)
        
        context['prjrequests'] = list()
        context['newprojects'] = list()
        prjreq_list = PrjRequest.objects.filter(registration=self.get_object())
        for prj_req in prjreq_list:
            if prj_req.project.projectid:
                if prj_req.flowstatus == PSTATUS_REG:
                    stlabel = _("Registered")
                elif prj_req.flowstatus == PSTATUS_PENDING:
                    stlabel = _("Pending")
                elif prj_req.flowstatus == PSTATUS_APPR:
                    stlabel = _("Approved")
                elif prj_req.flowstatus == PSTATUS_REJ:
                    stlabel = _("Rejected")
                
                tmps = "%s [%s]" % (prj_req.project.projectname, stlabel)
                context['prjrequests'].append(tmps)
            else:
                context['newprojects'].append(prj_req.project.projectname)


        if context['processinglevel'] == RSTATUS_PENDING:
            context['processingtitle'] = _('Pre-check registration')
        else:
            context['processingtitle'] = _('Approve registration')

        return context

    def get_initial(self):
        return {
            'regid' : self.get_object().regid,
            'username' : self.get_object().username
        }


class ApproveView(workflows.WorkflowView):
    workflow_class = ApproveRegWorkflow
    
    def get_initial(self):
        initial = super(ApproveView, self).get_initial()
        
        regid = int(self.kwargs['rowid'])
        initial['regid'] = regid
        
        reg_item = Registration.objects.get(regid=regid)
        initial['username'] = reg_item.username
        initial['userid'] = reg_item.userid
        
        return initial

