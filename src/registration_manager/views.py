import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
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

from .tables import RegisterTable
from .forms import ProcessRegForm

LOG = logging.getLogger(__name__)


class IndexView(tables.DataTableView):
    table_class = RegisterTable
    template_name = 'admin/registration_manager/reg_manager.html'

    def get_data(self):
    
        query1 = Q(regid__in=RegRequest.objects.all().values_list('registration'))
        query2 = Q(regid__in=PrjRequest.objects.all().values_list('registration'))
        
        #
        # TODO paging
        #
        return Registration.objects.filter(query1 | query2).order_by('username')


class RegReqItem:
    
    def __init__(self, regid):
    
        registration = Registration.objects.get(regid=regid)
        
        self.regid = regid
        self.username = registration.username
        self.reqlevel = RSTATUS_CHECKED
        self.extaccounts = list()
        self.reqprojects = list()
        self.newprojects = list()
        self.contacts = list()
        
        regreq_list = RegRequest.objects.filter(registration=registration)
        if len(regreq_list):
            for reg_req in regreq_list:
                if reg_req.externalid:
                    self.extaccounts.append(reg_req.externalid)
                self.reqlevel = min(self.reqlevel, reg_req.flowstatus)
                self.contacts.append(reg_req.contactper)
        else:
            self.reqlevel = RSTATUS_PRECHKD

        prj_mark = True
        found_guest = False
        prjreq_list = PrjRequest.objects.filter(registration=registration)
        for prj_req in prjreq_list:
            if prj_req.project.projectid:
                if prj_req.flowstatus == PSTATUS_PENDING or \
                    prj_req.flowstatus == PSTATUS_REG:
                    prj_mark = False
                if prj_req.project.status == PRJ_GUEST:
                    found_guest = True
                tmpt = (prj_req.project.projectname, prj_req.flowstatus)
                self.reqprojects.append(tmpt)
            else:
                self.newprojects.append(prj_req.project.projectname)
                
        if prj_mark and self.reqlevel == RSTATUS_PRECHKD:
            self.reqlevel = RSTATUS_CHECKED
        
        if self.reqlevel == RSTATUS_PENDING and len(self.newprojects) \
            and len(self.reqprojects) == 0:
            self.reqlevel = RSTATUS_NOFLOW

        if self.reqlevel == RSTATUS_PENDING and len(self.newprojects) == 0 \
            and len(self.reqprojects) == 1 and found_guest:
            self.reqlevel = RSTATUS_NOFLOW

def pstatus2label(flowstatus):
    if flowstatus == PSTATUS_REG:
        return _("Registered")
    if flowstatus == PSTATUS_PENDING:
        return _("Pending")
    if flowstatus == PSTATUS_APPR:
        return _("Approved")
    return _("Rejected")

def get_pstatus_descr(tmpt):
    return "%s [%s]" % (tmpt[0], pstatus2label(tmpt[1]))

class ProcessView(forms.ModalFormView):
    form_class = ProcessRegForm
    template_name = 'admin/registration_manager/reg_process.html'
    success_url = reverse_lazy('horizon:admin:registration_manager:index')
    
    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                self._object = RegReqItem(int(self.kwargs['regid']))
            except Exception:
                LOG.error("Registration error", exc_info=True)
                redirect = reverse_lazy("horizon:admin:registration_manager:index")
                exceptions.handle(self.request, _('Unable approve registration.'),
                                  redirect=redirect)
        return self._object

    def get_context_data(self, **kwargs):
        context = super(ProcessView, self).get_context_data(**kwargs)
        context['regid'] = self.get_object().regid
        context['username'] = self.get_object().username
        context['extaccounts'] = self.get_object().extaccounts
        context['processinglevel'] = self.get_object().reqlevel
        context['prjrequests'] = map(get_pstatus_descr, self.get_object().reqprojects)
        context['newprojects'] = self.get_object().newprojects
        context['contacts'] = self.get_object().contacts

        if context['processinglevel'] == RSTATUS_PENDING:
            context['processingtitle'] = _('Pre-check registrations')
        elif context['processinglevel'] == RSTATUS_PRECHKD:
            context['processingtitle'] = _('Pre-check project subscriptions')
        else:
            context['processingtitle'] = _('Approve registrations')

        return context

    def get_initial(self):
        return {
            'regid' : self.get_object().regid,
            'username' : self.get_object().username,
            'processinglevel' : self.get_object().reqlevel
        }



