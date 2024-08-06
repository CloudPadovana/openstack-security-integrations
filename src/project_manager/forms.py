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
from django.db import IntegrityError
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.views.decorators.debug import sensitive_variables
from django.utils.translation import gettext as _

from horizon import forms
from horizon import messages

from openstack_dashboard.api import keystone as keystone_api

from openstack_auth_shib.models import OS_SNAME_LEN
from openstack_auth_shib.models import OS_LNAME_LEN
from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PRJ_PUBLIC
from openstack_auth_shib.models import PRJ_PRIVATE
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_CHK_COMP
from openstack_auth_shib.models import PRJ_COURSE
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import PSTATUS_RENEW_DISC
from openstack_auth_shib.notifications import notifyProject
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import USER_NEED_RENEW
from openstack_auth_shib.notifications import NEWPRJ_REQ_TYPE
from openstack_auth_shib.notifications import MEMBER_REQUEST
from openstack_auth_shib.notifications import COMP_CHECK_TYPE
from openstack_auth_shib.utils import TAG_REGEX
from openstack_auth_shib.utils import PRJ_REGEX
from openstack_auth_shib.utils import getProjectInfo
from openstack_auth_shib.utils import get_year_list
from openstack_auth_shib.utils import NOW
from openstack_auth_shib.utils import FROMNOW
from openstack_auth_shib.utils import PREG_ATT_MAP
from openstack_auth_shib.utils import YEARS_RANGE

from openstack_auth_shib.models import NEW_MODEL
if NEW_MODEL:
    from openstack_auth_shib.models import PrjAttribute
    from openstack_auth_shib.utils import COURSE_ATT_MAP
    from django.forms.widgets import SelectDateWidget
else:
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
        if NEW_MODEL:
            if self.request.user.tenant_id != data['projectid']:
                raise ValidationError(_("Invalid project"))

            if not 'notes' in data:
                data['notes'] = ""

            try:
                data['org'] = 'unipd.it'
                data['ou'] = 'other'

                kclient = keystone_api.keystoneclient(self.request)
                for p_tag in kclient.projects.list_tags(c_prj.projectid):
                    if p_tag.startswith('OU='):
                        data['ou'] = p_tag[3:]
                    if p_tag.startswith('O='):
                        data['org'] = p_tag[2:]                
            except:
                LOG.error("Missing organization or unit", exc_info=True)
                raise ValidationError(_("Cannot retrieve data for course"))
        else:
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

                if NEW_MODEL:
                    c_info = PrjAttribute.objects.filter(project = c_prj, name__in = COURSE_ATT_MAP.keys())

                    need_update = (len(c_info) == 0)
                    for item in c_info:
                        if item.value != data[COURSE_ATT_MAP[item.name]]:
                            need_update = True
                            break;

                    if need_update:
                        if len(c_info) > 0:
                            c_info.delete()
                        for k_item, v_item in COURSE_ATT_MAP.items():
                            PrjAttribute(project = c_prj, name = k_item, value = data[v_item]).save()
                else:
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

class ProposedRenewForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ProposedRenewForm, self).__init__(request, *args, **kwargs)

        self.fields['projectid'] = forms.CharField(
            widget = HiddenInput,
            initial = request.user.tenant_id
        )

        self.fields['action'] = forms.CharField(
            widget = HiddenInput,
            initial = 'discard'
        )

    def clean(self):
        data = super(ProposedRenewForm, self).clean()
        if not data['action'] in [ 'renew', 'discard' ]:
             raise ValidationError(_('Bad action %s') % data['action'])
        return data
    
    @sensitive_variables('data')
    def handle(self, request, data):

        q_args = {
            'registration__userid' : request.user.id,
            'project__projectid' : request.user.tenant_id
        }
        prj_mails = None

        try:
            with transaction.atomic():
                if data['action'] == 'renew':
                    PrjRequest.objects.filter(**q_args).update(flowstatus = PSTATUS_RENEW_MEMB)

                    tmp_ad = PrjRole.objects.filter(project__projectid = request.user.tenant_id)
                    tmp_el = EMail.objects.filter(registration__in = [ x.registration for x in tmp_ad ])
                    prj_mails = [ y.email for y in tmp_el ]
                    messages.info(request, _("Renewal request sent to the project administrators"))
                else:
                    PrjRequest.objects.filter(**q_args).update(flowstatus = PSTATUS_RENEW_DISC)
                    messages.info(request, _("Your membership will be cancelled at the expiration date"))
                    return True

        except:
            LOG.error("Cannot process proposed renewal", exc_info=True)
            messages.error(request, _("Cannot process proposed renewal"))
            return False

        try:
            noti_params = {
                'username' : request.user.username,
                'project' : request.user.tenant_name
            }
            if prj_mails:
                notifyProject(prj_mails, USER_NEED_RENEW,
                              noti_params, user_id=request.user.id,
                              project_id=request.user.tenant_id,
                              dst_project_id=request.user.tenant_id)
        except:
            LOG.error("Cannot notify %s" % request.user.username, exc_info=True)

        return True



class SubscribeForm(forms.SelfHandlingForm):

    def __init__(self, *args, **kwargs):
        super(SubscribeForm, self).__init__(*args, **kwargs)

        self.fields['prjaction'] = forms.ChoiceField(
            label = _('Project action'),
            choices = [ ('newprj', _('Create new project')), ],
            widget = forms.Select(attrs = {
                'class': 'switchable',
                'data-slug': 'actsource'
            })
        )

        self.fields['newprj'] = forms.CharField(
            label = _('Personal project'),
            max_length = OS_SNAME_LEN,
            required = False,
            widget = forms.TextInput(attrs = {
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Project name')
            })
        )

        self.fields['prjdescr'] = forms.CharField(
            label = _("Project description"),
            required = False,
            widget = forms.widgets.Textarea(attrs = {
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Project description')
            })
        )

        self.fields['selprj'] = forms.MultipleChoiceField(
            label = _('Available projects'),
            required = False,
            widget = forms.SelectMultiple(attrs = {
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-selprj': _('Select existing project')
            }),
        )

        if NEW_MODEL:
            self.fields['expiration'] = forms.DateTimeField(
                label = _('Project expiration'),
                required = False,
                widget = SelectDateWidget(
                    attrs = {
                        'class': 'switched',
                        'data-switch-on': 'actsource',
                        'data-actsource-newprj': _('Project expiration')
                    }, 
                    years = get_year_list()),
                initial = FROMNOW(365)
            )

            self.fields['contactper'] = forms.CharField(
                label=_('Contact person'),
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'switched',
                    'data-switch-on': 'actsource',
                    'data-actsource-newprj': _('Contact person')
                })
            )

        self.fields['notes'] = forms.CharField(
            label = _('Notes'),
            required = False,
            widget = forms.widgets.Textarea()
        )

        auth_prjs = [ pitem.name for pitem in self.request.user.authorized_tenants ]

        pendPReq = PrjRequest.objects.filter(registration__userid=self.request.user.id)
        self.pendingProjects = [ prjreq.project.projectname for prjreq in pendPReq ]
        excl_prjs = auth_prjs + self.pendingProjects

        prj_list = Project.objects.exclude(projectname__in=excl_prjs)
        prj_list = prj_list.filter(status__in=[PRJ_PUBLIC, PRJ_COURSE], projectid__isnull=False)

        prjEntries = [
            (prj_entry.projectname, prj_entry.projectname) for prj_entry in prj_list
        ]
        if len(prjEntries):
            self.fields['selprj'].choices = prjEntries
            self.fields['prjaction'].choices = [
                ('selprj', _('Select existing projects')),
                ('newprj', _('Create new project'))
            ]

    def clean(self):
        data = super(SubscribeForm, self).clean()

        if data['prjaction'] == 'newprj':
            if not data['newprj']:
                raise ValidationError(_('Project name is required.'))
            tmpm = PRJ_REGEX.search(data['newprj'])
            if tmpm:
                raise ValidationError(_('Bad character "%s" for project name.') % tmpm.group(0))
        elif data['prjaction'] == 'selprj':
            if not data['selprj']:
                raise ValidationError(_('Missing selected project.'))

        if NEW_MODEL:
            now = NOW()
            if data['expiration'].date() < now.date():
                raise ValidationError(_('Invalid expiration time.'))
            if data['expiration'].year > now.year + YEARS_RANGE:
                raise ValidationError(_('Invalid expiration time.'))

            if not 'contactper' in data:
                data['contactper'] = ""

        return data

    @sensitive_variables('data')
    def handle(self, request, data):

        noti_buffer = list()

        with transaction.atomic():
        
            registration = Registration.objects.filter(userid=request.user.id)[0]
        
            prj_action = data['prjaction']
            prjlist = list()
            if prj_action == 'selprj':
                for project in data['selprj']:
                    prjlist.append((project, "", PRJ_PUBLIC, False))
            
            elif prj_action == 'newprj':
                prjlist.append((
                    data['newprj'],
                    data['prjdescr'],
                    PRJ_PUBLIC,
                    True
                ))
        
            for prjitem in prjlist:
        
                f_status = PSTATUS_PENDING
                if prjitem[3]:
                    try:

                        prjArgs = {
                            'projectname' : prjitem[0],
                            'description' : prjitem[1],
                            'status' : prjitem[2]
                        }
                        project = Project.objects.create(**prjArgs)

                        if NEW_MODEL:
                            for k_item, v_item in PREG_ATT_MAP.items():
                                PrjAttribute(project = project, name = k_item,
                                             value = str(data[v_item])).save()

                        noti_buffer.append({
                            'cloud_level' : True,
                            'action' : NEWPRJ_REQ_TYPE,
                            'context' : {
                                'username' : request.user.username,
                                'project' : project.projectname
                            }
                        })

                    except IntegrityError:
                        messages.error(request, _("Project %s already exists") % prjitem[0])
                        LOG.error("Cannot create project %s" % prjitem[0])
                        return False
                
                elif prjitem[0] in self.pendingProjects:
                    continue
                else:
                    project = Project.objects.get(projectname = prjitem[0])
                    if getProjectInfo(request, project)['comp_required']:

                        f_status = PSTATUS_CHK_COMP

                        noti_buffer.append({
                            'cloud_level' : True,
                            'action' : COMP_CHECK_TYPE,
                            'context' : {
                                'username' : request.user.username,
                                'project' : project.projectname
                            }
                        })
                    else:

                        admin_emails = list()
                        for prj_role in PrjRole.objects.filter(project = project):
                            for email_obj in EMail.objects.filter(registration = prj_role.registration):
                                admin_emails.append(email_obj.email)

                        noti_buffer.append({
                            'cloud_level' : False,
                            'action' : MEMBER_REQUEST,
                            'admin_emails' : admin_emails,
                            'context' : {
                                'username' : request.user.username,
                                'project' : project.projectname
                            }
                        })

                reqArgs = {
                    'registration' : registration,
                    'project' : project,
                    'flowstatus' : f_status,
                    'notes' : data['notes']
                }                
                reqPrj = PrjRequest(**reqArgs)
                reqPrj.save()

        for n_item in noti_buffer:
            if n_item['cloud_level']:
                #
                # Send notification to cloud admins for project creation or compliance check
                #
                notifyAdmin(request=self.request, action=n_item['action'], context=n_item['context'])
            else:
                #
                # Send notifications to project managers
                #
                notifyProject(request=self.request, rcpt=n_item['admin_emails'],
                              action=n_item['action'], context=n_item['context'])
                
        return True


