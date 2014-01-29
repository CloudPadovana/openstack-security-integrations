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

from .tables import RegisterTable
from .forms import ApproveRegForm
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

