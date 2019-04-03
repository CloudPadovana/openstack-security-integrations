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
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.views.decorators.debug import sensitive_variables
from django.utils.translation import ugettext as _

from horizon import forms
from horizon import messages

from openstack_auth_shib.models import OS_SNAME_LEN
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_COURSE

LOG = logging.getLogger(__name__)

class CourseForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(CourseForm, self).__init__(request, *args, **kwargs)

        self.fields['projectid'] = forms.CharField(widget=HiddenInput)
        
        self.fields['name'] = forms.CharField(
            label=_('Course name'),
            required=True,
            max_length=OS_SNAME_LEN
        )

        self.fields['description'] = forms.CharField(
            label=_('Course description'),
            required=True,
            widget=forms.widgets.Textarea()
        )

        self.fields['notes'] = forms.CharField(
            label=_('Notes'),
            required=False,
            widget=forms.widgets.Textarea()
        )

    def clean(self):
        data = super(CourseForm, self).clean()
        if '|' in data['name']:
            raise ValidationError(_('Bad character "|" in the course name.'))
        if '|' in data['description']:
            raise ValidationError(_('Bad character "|" in the course description.'))
        if '|' in data['notes']:
            raise ValidationError(_('Bad character "|" in the course notes.'))        
        return data

    @sensitive_variables('data')
    def handle(self, request, data):
        try:
            # TODO check for project_manager
            with transaction.atomic():
                c_prj = Project.objects.filter(projectid=data['projectid'])[0]
                new_descr = '%s|%s|%s' % (data['description'],
                                          data['name'],
                                          data['notes'])
                c_prj.description = new_descr
                c_prj.status = PRJ_COURSE
                c_prj.save()
        except:
            LOG.error("Cannot edit course parameters", exc_info=True)
            messages.error(request, _("Cannot edit course parameters"))
            return False

        return True

