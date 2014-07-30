#  Copyright (c) 2014 INFN - "Istituto Nazionale di Fisica Nucleare" - Italy
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License. 

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
