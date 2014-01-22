import logging

from horizon import forms

from django.db import transaction
from django.forms.widgets import HiddenInput
from openstack_auth_shib.models import UserMapping
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import Registration

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ApproveRegForm(forms.SelfHandlingForm):

    readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
    
    regid = forms.IntegerField(label=_("ID"), widget=readonlyInput)
    username = forms.CharField(label=_("User name"))
    email = forms.CharField(label=_("Email address"), widget=readonlyInput)
    notes = forms.CharField(label=_("Notes"), widget=readonlyInput)
    domain = forms.CharField(label=_("Domain"), widget=readonlyInput)
    region = forms.CharField(label=_("Region"), widget=readonlyInput)
    externalid = forms.CharField(label=_("External ID"), widget=readonlyInput, required=False)

    def __init__(self, request, *args, **kwargs):
        super(ApproveRegForm, self).__init__(request, *args, **kwargs)

    def handle(self, request, data):
        
        with transaction.commit_on_success():
            
            reg_request = RegRequest.objects.filter(registration__regid__exact=data.pop('regid'))
            #
            #TODO verify filter
            #
            #if data.pop('externalid'):
            #    self._object = usrReqList.filter(externalid__exact=data.pop('externalid'))[0]
            #else:
            #    self._object = usrReqList.filter(externalid__exact=None)[0]
            registr = reg_request[0].registration
            
            if registr.username <> data.pop('username'):
                registr.username = data.pop('username')
                registr.save()
        
        
            LOG.debug("Approving registration for %s (%s)" % (data.pop('username'), data.pop('password')))
            #
            #TODO call keystone
            #
        
            externalid = data.pop('externalid')
            if externalid:
                mapping = UserMapping(globaluser=externalid, registration=registr)
                mapping.save()
        
        return True



