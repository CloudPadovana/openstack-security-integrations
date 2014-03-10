import logging

from horizon import forms

from django.db import transaction
from django.forms.widgets import HiddenInput
from django.views.decorators.debug import sensitive_variables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PSTATUS_APPR
from openstack_auth_shib.models import PSTATUS_REJ

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ApproveSubscrForm(forms.SelfHandlingForm):

    readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
    
    regid = forms.IntegerField(label=_("ID"), widget=HiddenInput)
    username = forms.CharField(label=_("User name"), widget=readonlyInput)
    fullname = forms.CharField(label=_("Full name"), widget=readonlyInput)
    notes = forms.CharField(label=_("Notes"), widget=readonlyInput)
    checkaction = forms.CharField(widget=HiddenInput, initial='accept')

    @sensitive_variables('data')
    def handle(self, request, data):
    
        #
        # TODO check if the current user owns TENANTADMIN_ROLE (manual post)
        #
        
        
        with transaction.commit_on_success():
            
            LOG.debug("Approving subscription for %s" % data['username'])
                
            curr_prjname = self.request.user.tenant_name
            q_args = {
                'registration__regid' : int(data['regid']),
                'project__projectname' : curr_prjname
            }
                
            if data['checkaction'] == 'accept':
                new_status = PSTATUS_APPR
            else:
                new_status = PSTATUS_REJ
                    
            PrjRequest.objects.filter(**q_args).update(flowstatus=new_status)
        
        return True



