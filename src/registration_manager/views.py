import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy

from horizon import tables
from horizon import exceptions
from horizon import forms

from openstack_auth_shib.models import RegRequest

from .tables import RegisterTable
from .forms import ApproveRegForm

LOG = logging.getLogger(__name__)

def generateLocalAccount(registration):
    #
    # TODO improve suggested account (configurable)
    #
    if '@' in registration.username:
        uid = registration.username.split('@')[0]
    else:
        uid = registration.username
    
    return "%s:%09d" % (uid, registration.reqid)


class IndexView(tables.DataTableView):
    table_class = RegisterTable
    template_name = 'admin/registration_manager/reg_manager.html'

    def get_data(self):
    
        reg_list = []
        
        try:
            #
            # TODO paging
            #
            reg_list = RegRequest.objects.all()
        except Exception:
            exceptions.handle(self.request, _('Unable to retrieve registration list.'))

        return reg_list


class ApproveView(forms.ModalFormView):
    form_class = ApproveRegForm
    template_name = 'admin/registration_manager/reg_approve.html'
    success_url = reverse_lazy('horizon:admin:registration_manager:index')

    def dispatch(self, *args, **kwargs):
        return super(ApproveView, self).dispatch(*args, **kwargs)

    def get_object(self):
        if not hasattr(self, "_object"):
            try:

                self._object = RegRequest.objects.get(reqid=self.kwargs['reqid'])

            except Exception:
                redirect = reverse("horizon:admin:registration_manager:index")
                exceptions.handle(self.request,
                                  _('Unable to approve registration.'),
                                  redirect=redirect)
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ApproveView, self).get_context_data(**kwargs)
        context['registration'] = self.get_object()
        return context

    def get_initial(self):
        registration = self.get_object()
        return {
            'reqid' : registration.reqid ,
            'username' : registration.username,
            'password' : registration.password,
            'email' : registration.email ,
            'notes' : registration.notes ,
            'domain' : registration.domain,
            'region' : registration.region,
            'localaccount' : generateLocalAccount(registration)
        }



