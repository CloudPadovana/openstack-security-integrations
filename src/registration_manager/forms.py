import logging

from horizon import forms
from django.forms.widgets import HiddenInput

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ApproveRegForm(forms.SelfHandlingForm):

    readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
    
    reqid = forms.CharField(label=_("Request ID"), widget=readonlyInput)
    localuser = forms.CharField(label=_("Cloud User"), widget=readonlyInput)
    password = forms.CharField(widget=HiddenInput)
    email = forms.CharField(label=_("Email address"), widget=readonlyInput)
    notes = forms.CharField(label=_("Notes"), widget=readonlyInput)
    globalid = forms.CharField(label=_("Global user ID"), widget=readonlyInput)
    idp = forms.CharField(label=_("Identity Provider"), widget=readonlyInput)
    domain = forms.CharField(label=_("Domain"), widget=readonlyInput)

    def __init__(self, request, *args, **kwargs):
        super(ApproveRegForm, self).__init__(request, *args, **kwargs)

    def handle(self, request, data):
        
        LOG.debug("Approving registration for %s" % data.pop('reqid'))
        
        return True



