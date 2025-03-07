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
import re

from horizon import forms
from horizon.utils import validators

from django import shortcuts
from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_variables
from django.db import transaction, IntegrityError

from .idpmanager import get_logout_url
from .idpmanager import postproc_logout
from .models import Registration
from .models import Project
from .models import RegRequest
from .models import PrjRequest
from .models import UserMapping
from .models import Expiration
from .models import PRJ_PRIVATE
from .models import PRJ_PUBLIC
from .models import OS_LNAME_LEN
from .models import OS_SNAME_LEN
from .models import PWD_LEN
from .models import EMAIL_LEN
from .models import DESCR_LEN
from .models import PSTATUS_REG
from .models import PSTATUS_PENDING
from .notifications import notifyAdmin, REGISTR_AVAIL_TYPE
from .utils import get_ostack_attributes
from .utils import check_projectname
from .utils import get_year_list
from .utils import MAX_RENEW
from .utils import NOW
from .utils import FROMNOW
from .utils import ATT_PRJ_EXP
from .utils import ATT_PRJ_CPER
from .utils import ATT_PRJ_ORG
from .utils import ATT_PRJ_OU

from .models import NEW_MODEL
if NEW_MODEL:
    from .models import PrjAttribute
    from .utils import ATT_PRJ_CIDR
    from .utils import ATT_PRJ_ORG
    from django.forms.widgets import SelectDateWidget

LOG = logging.getLogger(__name__)

MARK_COMP_ON = 'c:'
MARK_COMP_OFF = 'f:'

class RegistrForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):

        super(RegistrForm, self).__init__(request, *args, **kwargs)
        
        self.registr_err = None

        initial = kwargs['initial'] if 'initial' in kwargs else dict()

        #################################################################################
        # Account section
        #################################################################################

        username_attrs = {'readonly': 'readonly'} if 'username' in initial else {}
        self.fields['username'] = forms.CharField(
            label=_('User name'),
            max_length=OS_LNAME_LEN,
            widget=forms.TextInput(attrs=username_attrs)
        )

        self.fields['federated'] = forms.CharField(
            max_length=OS_LNAME_LEN,
            widget=forms.HiddenInput
        )

        gname_attrs = {'readonly': 'readonly'} if 'givenname' in initial else {}
        self.fields['givenname'] = forms.CharField(
            label=_('First name'),
            max_length=OS_LNAME_LEN,
            widget=forms.TextInput(attrs=gname_attrs)
        )

        sname_attrs = {'readonly': 'readonly'} if 'sn' in initial else {}
        self.fields['sn'] = forms.CharField(
            label=_('Last name'),
            max_length=OS_LNAME_LEN,
            widget=forms.TextInput(attrs=sname_attrs)
        )
        
        if initial['needpwd']:
            self.fields['pwd'] = forms.RegexField(
                label=_("Password"),
                max_length=PWD_LEN,
                widget=forms.PasswordInput(render_value=False),
                regex=validators.password_validator(),
                error_messages={'invalid': validators.password_validator_msg()}
            )
            
            self.fields['repwd'] = forms.CharField(
                label=_("Confirm Password"),
                max_length=PWD_LEN,
                widget=forms.PasswordInput(render_value=False)
            )

        mail_attrs = {'readonly': 'readonly'} if 'email' in initial else {}
        self.fields['email'] = forms.EmailField(
            label=_('Email Address'),
            max_length=EMAIL_LEN,
            widget=forms.TextInput(attrs=mail_attrs)
        )

        #################################################################################
        # Projects section
        #################################################################################

        org_table = settings.HORIZON_CONFIG.get('organization', {})
        org_combo = [ ('-','-') ]
        ou_combo = [ ('-','-') ]
        for org_name, ou_list in org_table.items():
            org_combo.append((org_name, org_name))
            for ou_data in ou_list:
                ou_combo.append((ou_data[0], ou_data[0]))

        if 'projectname' in request.GET or 'selcourse' in request.POST:

            self.fields['prjaction'] = forms.CharField(
                label = _('Project action'),
                initial = 'selprj',
                widget = forms.HiddenInput
            )

            self.fields['selcourse'] = forms.CharField(
                label = "Selected course",
                initial = request.GET.get('projectname', ''),
                widget=forms.HiddenInput
            )

        else:

            self.fields['prjaction'] = forms.ChoiceField(
                label=_('Project action'),
                choices = [
                    ('selprj', _('Select existing projects')),
                    ('newprj', _('Create new project'))
                ],
                widget=forms.Select()
            )

            self.fields['newprj'] = forms.CharField(
                label=_('Project name'),
                max_length=OS_SNAME_LEN,
                required=False,
                widget=forms.TextInput()
            )

            self.fields['prjdescr'] = forms.CharField(
                label=_("Project description"),
                required=False,
                max_length=DESCR_LEN,
                widget=forms.widgets.Textarea()
            )

            self.fields['contactper'] = forms.CharField(
                label=_('Project supervisor or reference'),
                required=False,
                widget=forms.TextInput()
            )

            if NEW_MODEL:
                self.fields['expiration'] = forms.DateTimeField(
                    label = _('Project expiration'),
                    required = False,
                    widget = SelectDateWidget(years = get_year_list()),
                    initial = FROMNOW(365)
                )

            self.fields['selprj'] = forms.MultipleChoiceField(
                label=_('Available projects'),
                required=False,
                choices=self._avail_prj_entries(),
                widget=forms.SelectMultiple(),
            )

            self.fields['organization'] = forms.ChoiceField(
                label = _('Home institution for project'),
                required = False,
                choices = org_combo
            )

            self.fields['org_unit'] = forms.ChoiceField(
                label = _('Unit or department for project'),
                required = False,
                choices = ou_combo
            )

        self.fields['notes'] = forms.CharField(
            label=_('Notes'),
            required=False,
            widget=forms.widgets.Textarea()
        )
    
        self.fields['aupok'] = forms.CharField(
            widget=forms.HiddenInput,
            initial='reject'
        )

    def _avail_prj_entries(self):
        avail_prjs = list()

        with transaction.atomic():
            c_projects = set()
            if NEW_MODEL:
                # TODO use utils.getProjectInfo (cleanup code required)
                comp_rules = getattr(settings, 'COMPLIANCE_RULES', {})

                cidr_list = comp_rules.get('subnets', [])
                for p_item in PrjAttribute.objects.filter(name = ATT_PRJ_CIDR):
                    if p_item.value in cidr_list:
                        c_projects.add(p_item.project.projectname)

                org_list = comp_rules.get('organizations', [])
                for p_item in PrjAttribute.objects.filter(name = ATT_PRJ_ORG):
                    if p_item.value in org_list:
                        c_projects.add(p_item.project.projectname)

            q_args = {
                'projectid__isnull' : False,
                'status__gt' : PRJ_PRIVATE
            }
            for prj_entry in Project.objects.filter(**q_args):
                prj_label = prj_entry.projectname

                if prj_entry.projectname in c_projects:
                    avail_prjs.append((MARK_COMP_ON + prj_label, prj_label))
                else:
                    avail_prjs.append((MARK_COMP_OFF + prj_label, prj_label))

        return avail_prjs
        

    def clean(self):
        data = super(RegistrForm, self).clean()
        org_table = settings.HORIZON_CONFIG.get('organization', {})

        LOG.debug("Registration posted data: %s" % str(data))
        
        if data['prjaction'] == 'newprj':

            data['newprj'] = check_projectname(data['newprj'], ValidationError)

        elif data['prjaction'] == 'selprj':
            if not 'selprj' in data:
                tmpc = data.get('selcourse', None)
                if not tmpc:
                    raise ValidationError(_('Missing selected project.'))
                data['selprj'] = [ tmpc ]
        else:
            raise ValidationError(_('Wrong project parameter.'))
        
        if data.get('aupok', 'reject') != 'accept':
            raise ValidationError(_('You must accept Cloud Padovana AUP.'))
            
        if 'pwd' in data and data['pwd'] != data.get('repwd', None):
                raise ValidationError(_('Passwords do not match.'))

        if '@' in data['username'] or ':' in data['username']:
            if data.get('federated', 'false') == 'false':
                raise ValidationError(_("Invalid characters in user name (@:)"))

        if NEW_MODEL and 'expiration' in data:
            now = NOW()
            if data['expiration'].date() < now.date():
                raise ValidationError(_('Invalid expiration time.'))
            if data['expiration'].year > now.year + MAX_RENEW:
                raise ValidationError(_('Invalid expiration time.'))

        p_list = list()
        for item in data['selprj']:
            if item.startswith(MARK_COMP_ON) or item.startswith(MARK_COMP_OFF):
                p_list.append(item[2:])
            else:
                p_list.append(item)
        data['selprj'] = p_list

        LOG.debug("New posted data: %s" % str(data))
        return data

    def _build_safe_redirect(self, request, location):
        safe_loc = get_logout_url(request, location)
        if safe_loc and settings.HORIZON_CONFIG.get('enable_slo', False):
            response = shortcuts.redirect(safe_loc)
            response = postproc_logout(request, response)
        else:
            safe_loc = location
            response = shortcuts.redirect(location)
        
        #
        # See note in horizon.forms.ModalFormView
        #
        response['X-Horizon-Location'] = safe_loc
            
        return response

    @sensitive_variables('data')
    def handle(self, request, data):

        domain, auth_url = get_ostack_attributes(request)
        
        try:
            pwd = data.get('pwd', None)
            
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

            LOG.debug("Saving %s" % data['username'])
                    
            with transaction.atomic():

                is_fed_account = data.get('federated', 'false') == 'true'
                prj_flowstatus = PSTATUS_REG

                # test for course account
                registration = None
                if is_fed_account:
                    tmpm = UserMapping.objects.filter(globaluser=data['username'])
                    registration = tmpm[0].registration if len(tmpm) > 0 else None
            
                if registration:

                    q_args = {
                        'registration' : registration,
                        'project__projectname__in' : [ x[0] for x in prjlist ]
                    }
                    if Expiration.objects.filter(**q_args).count() > 0:
                        return self._build_safe_redirect(request, 
                                                '/dashboard/auth/already_subscribed/')

                    if PrjRequest.objects.filter(**q_args).count() > 0:
                        return self._build_safe_redirect(request, 
                                                '/dashboard/auth/dup_login/')

                    prj_flowstatus = PSTATUS_PENDING

                else:

                    if RegRequest.objects.filter(externalid=data['username']).count():
                        raise ValidationError("Request already sent")

                    queryArgs = {
                        'username' : data['username'],
                        'givenname' : data['givenname'],
                        'sn' : data['sn'],
                        'organization' : data.get('organization', ''),
                        'phone' : '0000',
                        'domain' : domain
                    }
                    registration = Registration(**queryArgs)
                    registration.save()

                    regArgs = {
                        'registration' : registration,
                        'password' : pwd,
                        'email' : data['email'],
                        'contactper' : data.get('contactper', ''),
                        'notes' : data['notes']
                    }
                    if is_fed_account:
                        regArgs['externalid'] = data['username']
                    regReq = RegRequest(**regArgs)
                    regReq.save()
                
                    LOG.debug("Saved %s" % data['username'])

                for prjitem in prjlist:
            
                    if prjitem[3]:

                        prjArgs = {
                            'projectname' : prjitem[0],
                            'description' : prjitem[1],
                            'status' : prjitem[2]
                        }
                        project = Project.objects.create(**prjArgs)

                        if NEW_MODEL:
                            PrjAttribute(project = project, name = ATT_PRJ_EXP,
                                         value = data['expiration'].isoformat()).save()
                            PrjAttribute(project = project, name = ATT_PRJ_CPER,
                                         value = data['contactper']).save()
                            PrjAttribute(project = project, name = ATT_PRJ_ORG,
                                         value = data['organization']).save()
                            PrjAttribute(project = project, name = ATT_PRJ_OU,
                                         value = data['org_unit']).save()

                    else:
                        project = Project.objects.get(projectname=prjitem[0])
            
                    reqArgs = {
                        'registration' : registration,
                        'project' : project,
                        'flowstatus': prj_flowstatus,
                        'notes' : data['notes']
                    }
                    
                    reqPrj = PrjRequest(**reqArgs)
                    reqPrj.save()

            noti_params = {
                'username': data['username'],
                'projects': list(p[0] for p in prjlist),
                'project_creation': (prj_action == 'newprj'),
                'notes' : data['notes'],
                'contactper' : data.get('contactper', '')
            }
            notifyAdmin(request=self.request, action=REGISTR_AVAIL_TYPE, context=noti_params)

            # Don't user reverse_lazy
            # It is necessary to get out of the protected area
            return self._build_safe_redirect(request, '/dashboard/auth/reg_done/')
        
        except ValidationError:
        
            return self._build_safe_redirect(request, '/dashboard/auth/dup_login/')
            
        except IntegrityError:
        
            return self._build_safe_redirect(request, '/dashboard/auth/name_exists/')

        except:
        
            LOG.error("Generic failure", exc_info=True)

        return self._build_safe_redirect(request, '/dashboard/auth/reg_failure/')


