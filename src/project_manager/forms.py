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

from django.conf import settings
from django.db import transaction
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.views.decorators.debug import sensitive_variables
from django.utils.translation import ugettext as _

from horizon import forms
from horizon import messages

from openstack_dashboard.api import keystone as keystone_api

from openstack_auth_shib.models import OS_SNAME_LEN
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRole
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

        ou_choices = self._get_OU_list()
        if len(ou_choices) > 0:
            self.fields['ou'] = forms.ChoiceField(
                label=_('Department'),
                required=True,
                choices=ou_choices
            )
        else:
            self.fields['ou'] = forms.CharField(
                required=True,
                initial="other",
                widget=forms.HiddenInput
            )

    def _get_OU_list(self):
        result = list()
        org_table = settings.HORIZON_CONFIG.get('organization', {})
        for korg in settings.HORIZON_CONFIG.get('course_for', {}).keys():
            result += org_table[korg]
        return result

    def clean(self):
        data = super(CourseForm, self).clean()
        if '|' in data['name']:
            raise ValidationError(_('Bad character "|" in the course name.'))
        if '|' in data['description']:
            raise ValidationError(_('Bad character "|" in the course description.'))
        if '|' in data['notes']:
            raise ValidationError(_('Bad character "|" in the course notes.'))        
        if '|' in data['ou']:
            raise ValidationError(_('Bad character "|" in the course department.'))
        return data

    @sensitive_variables('data')
    def handle(self, request, data):
        try:

            with transaction.atomic():
                c_prj = Project.objects.filter(projectid=data['projectid'])[0]

                if PrjRole.objects.filter(registration__userid = request.user.id,
                                          project = c_prj).count() == 0:
                    messages.error(request, _("Operation not allowed"))
                    return False

                new_descr = '%s|%s|%s|%s' % (data['description'], data['name'],
                                             data['notes'], data['ou'])
                c_prj.description = new_descr
                c_prj.status = PRJ_COURSE
                c_prj.save()

        except:
            LOG.error("Cannot edit course parameters", exc_info=True)
            messages.error(request, _("Cannot edit course parameters"))
            return False

        return True

class EditTagsForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(EditTagsForm, self).__init__(request, *args, **kwargs)

        self.fields['projectid'] = forms.CharField(widget=HiddenInput)

        self.fields['taglist'] = forms.CharField(
            label=_('Tag list (comma separated)'),
            required=True,
            widget=forms.widgets.Textarea()
        )

    def clean(self):
        data = super(EditTagsForm, self).clean()

        if '/' in data['taglist']:
            raise ValidationError(_('Bad character "/" in the tag list.'))

        new_list = list()
        for item in data['taglist'].split(','):
            tmps = item.strip()
            if len(tmps) > 255:
                raise ValidationError(_('Tag too long.'))
            new_list.append(tmps)
        data['ptags'] = new_list

        return data

    @sensitive_variables('data')
    def handle(self, request, data):
        try:

            kclient = keystone_api.keystoneclient(request)
            
            kclient.projects.update_tags(data['projectid'], data['ptags'])

        except:
            LOG.error("Cannot edit tags", exc_info=True)
            messages.error(request, _("Cannot edit tags"))
            return False

        return True





