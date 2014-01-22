import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy

from horizon import tables
from horizon import exceptions
from horizon import forms

from openstack_auth_shib.models import Registration, RegRequest

from .tables import RegisterTable
from .forms import ApproveRegForm

LOG = logging.getLogger(__name__)

#def generateLocalAccount(registration):
#    #
#    # TODO improve suggested account (configurable)
#    #
#    if '@' in registration.username:
#        uid = registration.username.split('@')[0]
#    else:
#        uid = registration.username
#    
#    return "%s:%09d" % (uid, registration.reqid)

class RegistEntry:

    def __init__(self, reg_request):
            self.regid = reg_request.registration.regid
            self.username = reg_request.registration.username
            self.password = reg_request.password
            self.email = reg_request.email
            self.notes = reg_request.notes
            self.externalid = reg_request.externalid
            self.domain = reg_request.registration.domain
            self.region = reg_request.registration.region

    def getDataAsDict(self):
        return {
            'regid' : self.regid,
            'username' : self.username,
            'password' : self.password,
            'email' : self.email,
            'notes' : self.notes,
            'externalid' : self.externalid,
            'domain' : self.domain,
            'region' : self.region
        }
    
    def getID(self):
        if self.externalid:
            return "%s:%d" % (self.externalid, self.regid)
        else:
            return "none:%d" % self.regid



class IndexView(tables.DataTableView):
    table_class = RegisterTable
    template_name = 'admin/registration_manager/reg_manager.html'

    def get_data(self):
    
        try:
            #
            # TODO paging
            #
            return map(RegistEntry, RegRequest.objects.all())
            
        except Exception:
            exceptions.handle(self.request, _('Unable to retrieve registration list.'))

        return list()


class ApproveView(forms.ModalFormView):
    form_class = ApproveRegForm
    template_name = 'admin/registration_manager/reg_approve.html'
    success_url = reverse_lazy('horizon:admin:registration_manager:index')

    def dispatch(self, *args, **kwargs):
        return super(ApproveView, self).dispatch(*args, **kwargs)

    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                extid, strregid = self.kwargs['rowid'].split(':')
                
                usrReqList = RegRequest.objects.filter(registration__regid__exact=int(strregid))
                
                #
                #TODO verify filter
                #
                #if extid:
                #    self._object = usrReqList.filter(externalid__exact=extid)[0]
                #else:
                #    self._object = usrReqList.filter(externalid__exact=None)[0]
                self._object = RegistEntry(usrReqList[0])
                
            except Exception:
                LOG.error("Failure on registration", exc_info=True)
                redirect = reverse("horizon:admin:registration_manager:index")
                exceptions.handle(self.request,
                                  _('Unable to approve registration.'),
                                  redirect=redirect)
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ApproveView, self).get_context_data(**kwargs)
        context['reg_reference'] = self.get_object().getID()
        return context

    def get_initial(self):
        return self.get_object().getDataAsDict()



