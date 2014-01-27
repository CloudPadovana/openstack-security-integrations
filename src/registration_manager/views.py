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
    
        result = list()
        
        try:
            #
            # TODO paging
            #
            r_list = Registration.objects.all();

            for r_entry in r_list:
                nRReq = RegRequest.objects.filter(registration__regid__exact=r_entry.regid).count()
                nPReq = PrjRequest.objects.filter(registration__regid__exact=r_entry.regid).count()
                
                if nRReq > 0 or nPReq:
                    result.append(r_entry)
            
        except Exception:
            exceptions.handle(self.request, _('Unable to retrieve registration list.'))

        return result


class ApproveView(workflows.WorkflowView):
    workflow_class = ApproveRegWorkflow
    
    def get_initial(self):
        initial = super(ApproveView, self).get_initial()
        
        regid = int(self.kwargs['rowid'])
        initial['regid'] = regid
        return initial

