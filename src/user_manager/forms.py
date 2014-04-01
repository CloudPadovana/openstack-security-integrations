import logging

from django.db import transaction
from django.forms.widgets import HiddenInput
from django.forms.extras.widgets import SelectDateWidget
from django.utils.translation import ugettext as _

from horizon import forms

from openstack_auth_shib.models import Registration

LOG = logging.getLogger(__name__)

class RenewExpForm(forms.SelfHandlingForm):

    userid = forms.CharField(
        label=_("User ID"), 
        widget=HiddenInput
    )
    expiration = forms.DateTimeField(
        label=_("Expiration date"),
        widget=SelectDateWidget
    )

    def handle(self, request, data):
        
        with transaction.commit_on_success():
        
            reg_list = Registration.objects.filter(userid=data['userid'])
            reg_list.update(expdate=data['expiration'])
            
        return True
