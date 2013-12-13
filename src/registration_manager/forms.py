import logging

from horizon import forms

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ApproveRegForm(forms.SelfHandlingForm):

    readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
    
    uname = forms.CharField(label=_("Global account id"), widget=readonlyInput)
    domain = forms.CharField(label=_("Domain"), widget=readonlyInput)
    project = forms.CharField(label=_("Project"), widget=readonlyInput)
    
    def __init__(self, request, *args, **kwargs):
        super(ApproveRegForm, self).__init__(request, *args, **kwargs)

    def handle(self, request, data):
        
        LOG.debug("Approving registration for %s" % data.pop('uname'))
        
        return True



