import logging

from horizon import forms

from django.db import transaction
from django.forms.widgets import HiddenInput
from django.views.decorators.debug import sensitive_variables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ApproveSubscrForm(forms.SelfHandlingForm):

    readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
    
    regid = forms.IntegerField(label=_("ID"), widget=HiddenInput)
    username = forms.CharField(label=_("User name"), widget=readonlyInput)
    fullname = forms.CharField(label=_("Full name"), widget=readonlyInput)
    notes = forms.CharField(label=_("Notes"), widget=readonlyInput)
    role_id = forms.ChoiceField(label=_("Role"))

    @sensitive_variables('data')
    def handle(self, request, data):
        
        with transaction.commit_on_success():
            
            LOG.debug("Approving subscription for %s" % data['username'])
        
        return True



