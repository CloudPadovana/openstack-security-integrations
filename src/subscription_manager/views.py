import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy

from horizon import tables
from horizon import exceptions
from horizon import forms

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PSTATUS_REG
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_APPR
from openstack_auth_shib.models import PSTATUS_REJ

from .tables import SubscriptionTable
from .forms import ApproveSubscrForm

LOG = logging.getLogger(__name__)

class PrjReqItem:
    def __init__(self, prjReq):
        self.regid = prjReq.registration.regid
        self.username = prjReq.registration.username
        self.givenname = prjReq.registration.givenname
        self.sn = prjReq.registration.sn
        self.notes = prjReq.notes
    

class IndexView(tables.DataTableView):
    table_class = SubscriptionTable
    template_name = 'project/subscription_manager/subscr_manager.html'

    def get_data(self):
    
        reqList = list()
        
        try:
            #
            # TODO paging
            #
            curr_prjname = self.request.user.tenant_name
            q_args = {
                'project__projectname' : curr_prjname,
                'flowstatus' : PSTATUS_PENDING
            }
            for p_entry in PrjRequest.objects.filter(**q_args):
                reqList.append(PrjReqItem(p_entry))
            
        except Exception:
            exceptions.handle(self.request, _('Unable to retrieve subscription list.'))

        return reqList


class ApproveView(forms.ModalFormView):
    form_class = ApproveSubscrForm
    template_name = 'project/subscription_manager/subscr_approve.html'
    success_url = reverse_lazy('horizon:project:subscription_manager:index')
    
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
                redirect = reverse_lazy("horizon:project:subscription_manager:index")
                exceptions.handle(self.request, _('Unable approve subscription.'),
                                  redirect=redirect)
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ApproveView, self).get_context_data(**kwargs)
        context['regid'] = self.get_object().regid
        return context

    def get_initial(self):
        return {
            'regid' : self.get_object().regid,
            'username' : self.get_object().username,
            'givenname' : self.get_object().givenname,
            'sn' : self.get_object().sn,
            'notes' : self.get_object().notes
        }

