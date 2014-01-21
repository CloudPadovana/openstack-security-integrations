import logging

from horizon import forms
from django.forms.widgets import HiddenInput
from openstack_auth_shib.models import UserMapping

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ApproveRegForm(forms.SelfHandlingForm):

    readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
    
    reqid = forms.CharField(label=_("Request ID"), widget=readonlyInput)
    username = forms.CharField(label=_("User name"), widget=readonlyInput)
    password = forms.CharField(widget=HiddenInput)
    email = forms.CharField(label=_("Email address"), widget=readonlyInput)
    notes = forms.CharField(label=_("Notes"), widget=readonlyInput)
    domain = forms.CharField(label=_("Domain"), widget=readonlyInput)
    region = forms.CharField(label=_("Region"), widget=readonlyInput)
    localaccount = forms.CharField(label=_("Local account"))

    def __init__(self, request, *args, **kwargs):
        super(ApproveRegForm, self).__init__(request, *args, **kwargs)

    def handle(self, request, data):
        
        LOG.debug("Approving registration for %s" % data.pop('reqid'))
        #
        #TODO call keystone
        #
        
        try:
            username = data.pop('username')
            localaccount = data.pop('localaccount')
            mapping = UserMapping(globaluser=username, localuser=localaccount)
            mapping.save()
        except:
            LOG.error("User mapping failure", exc_info=True)
        
        return True



