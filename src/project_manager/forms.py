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
from openstack_auth_shib.models import OS_LNAME_LEN
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PRJ_COURSE
from openstack_auth_shib.utils import TAG_REGEX
from openstack_auth_shib.utils import encode_course_info
from openstack_auth_shib.utils import check_course_info

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
        err_msg = check_course_info(data)
        if err_msg:
            raise ValidationError(err_msg)
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

                kclient = keystone_api.keystoneclient(request)
                for p_tag in kclient.projects.list_tags(c_prj.projectid):
                    if p_tag.startswith('OU='):
                        data['ou'] = p_tag[3:]
                    if p_tag.startswith('O='):
                        data['org'] = p_tag[2:]

                new_descr = encode_course_info(data)
                c_prj.description = new_descr
                c_prj.status = PRJ_COURSE
                c_prj.save()

        except:
            LOG.error("Cannot edit course parameters", exc_info=True)
            messages.error(request, _("Cannot edit course parameters"))
            return False

        return True

class CourseDetailForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(CourseDetailForm, self).__init__(request, *args, **kwargs)

        self.fields['courseref'] = forms.CharField(
            label=_('Course Link'),
            required=True,
            max_length=OS_LNAME_LEN,
            widget=forms.TextInput(attrs={'readonly': 'readonly'})
        )

    @sensitive_variables('data')
    def handle(self, request, data):
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

        new_list = list()
        for item in data['taglist'].split(','):
            tmps = item.strip()
            if len(tmps) > 255:
                raise ValidationError(_('Tag %s too long') % tmps)
            tmpm = TAG_REGEX.search(tmps)
            if not tmpm:
                raise ValidationError(_('Bad format for tag %s') % tmps)
            if tmps.startswith('ou='):
                new_list.append(tmps.replace('ou=', 'OU='))
            elif tmps.startswith('o='):
                new_list.append(tmps.replace('o=', 'O='))
            else:
                new_list.append(tmps)
        data['ptags'] = new_list

        return data

    @sensitive_variables('data')
    def handle(self, request, data):
        try:

            kclient = keystone_api.keystoneclient(request)
            kclient.projects.update_tags(data['projectid'], [])
            kclient.projects.update_tags(data['projectid'], data['ptags'])

        except:
            LOG.error("Cannot edit tags", exc_info=True)
            messages.error(request, _("Cannot edit tags"))
            return False

        return True





