import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy

from horizon import exceptions
from horizon import forms

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PSTATUS_REG
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_APPR
from openstack_auth_shib.models import PSTATUS_REJ

from .forms import ProjectRequestForm

LOG = logging.getLogger(__name__)

class RequestView(forms.ModalFormView):
    form_class = ProjectRequestForm
    template_name = 'project/project_requests/prj_request.html'
    success_url = reverse_lazy('horizon:project:overview:index')

