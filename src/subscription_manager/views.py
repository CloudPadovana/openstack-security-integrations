import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy

from horizon import tables
from horizon import exceptions
from horizon import forms

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_dashboard.api import keystone as keystone_api

from .tables import SubscriptionTable
from .forms import ApproveSubscrForm

LOG = logging.getLogger(__name__)

class PrjReqItem:
    def __init__(self, prjReq):
        self.regid = prjReq.registration.regid
        self.username = prjReq.registration.username
        self.fullname = prjReq.registration.fullname
        self.notes = prjReq.notes
    
    def get_initial(self):
        return {
            'regid' : self.regid,
            'username' : self.username,
            'fullname' : self.fullname,
            'notes' : self.notes
        }


class IndexView(tables.DataTableView):
    table_class = SubscriptionTable
    template_name = 'admin/registration_manager/reg_manager.html'

    def get_data(self):
    
        reqList = list()
        
        try:
            #
            # TODO paging
            #
            curr_prjname = self.request.user.tenant_name
            for p_entry in PrjRequest.objects.filter(project__projectname=curr_prjname):
                reqList.append(PrjReqItem(p_entry))
            
        except Exception:
            exceptions.handle(self.request, _('Unable to retrieve subscription list.'))

        return reqList


class ApproveView(forms.ModalFormView):
    form_class = ApproveSubscrForm
    template_name = 'project/subscription_manager/reg_approve.html'
    success_url = reverse_lazy('horizon:project:subscription_manager:index')
    
    def get_object(self):
        if not hasattr(self, "_object"):
            try:

                regid = int(self.kwargs['regid'])
                curr_prjname = self.request.user.tenant_name
                qSet = PrjRequest.objects.filter(project__projectname=curr_prjname)
                self._object = PrjReqItem(qSet.filter(registration__regid=regid)[0])
                
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
        ini_dict = self.get_object().get_initial()
        role_list = keystone_api.role_list(self.request)
        role_choices = [(role.id, role.name) for role in role_list]
        ini_dict['role_id'] = role_choices
        return ini_dict

