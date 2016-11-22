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

from horizon import forms
from horizon.utils import validators

from django import shortcuts
from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import ugettext as _
from django.views.decorators.debug import sensitive_variables
from django.db import transaction, IntegrityError

from .idpmanager import get_manager
from .models import Registration, Project, RegRequest, PrjRequest
from .models import PRJ_PRIVATE, PRJ_PUBLIC, PRJ_GUEST
from .models import OS_LNAME_LEN, OS_SNAME_LEN, PWD_LEN, EMAIL_LEN
from .notifications import notifyManagers, notification_render, REGISTR_AVAIL_TYPE
from .utils import import_guest_project, get_ostack_attributes

LOG = logging.getLogger(__name__)

class RegistrForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):

        super(RegistrForm, self).__init__(request, *args, **kwargs)
        
        self.registr_err = None

        initial = kwargs['initial'] if 'initial' in kwargs else dict()

        self.fields['username'] = forms.CharField(
            label=_('User name'),
            max_length=OS_LNAME_LEN,
            widget=forms.HiddenInput if 'username' in initial else forms.TextInput
        )
        
        self.fields['federated'] = forms.CharField(
            max_length=OS_LNAME_LEN,
            widget=forms.HiddenInput
        )

        self.fields['givenname'] = forms.CharField(
            label=_('First name'),
            max_length=OS_LNAME_LEN,
            widget=forms.HiddenInput if 'givenname' in initial else forms.TextInput
        )
            
        self.fields['sn'] = forms.CharField(
            label=_('Last name'),
            max_length=OS_LNAME_LEN,
            widget=forms.HiddenInput if 'sn' in initial else forms.TextInput
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
            
        self.fields['email'] = forms.EmailField(
            label=_('Email Address'),
            max_length=EMAIL_LEN,
            widget=forms.HiddenInput if 'email' in initial else forms.TextInput
        )

        self.fields['prjaction'] = forms.ChoiceField(
            label=_('Project action'),
            #choices = <see later>
            widget=forms.Select(attrs={
                'class': 'switchable',
                'data-slug': 'actsource'
            })
        )
    
        self.fields['newprj'] = forms.CharField(
            label=_('Personal project'),
            max_length=OS_SNAME_LEN,
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Project name')
            })
        )
        
        self.fields['prjdescr'] = forms.CharField(
            label=_("Project description"),
            required=False,
            widget=forms.widgets.Textarea(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Project description')
            })
        )
        
        self.fields['prjpriv'] = forms.BooleanField(
            label=_("Private project"),
            required=False,
            initial=False,
            widget=forms.widgets.CheckboxInput(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Private project')
            })
        )
    
        self.fields['selprj'] = forms.MultipleChoiceField(
            label=_('Available projects'),
            required=False,
            widget=forms.SelectMultiple(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-selprj': _('Select existing project')
            }),
        )

        self.fields['organization'] = forms.CharField(
            label=_('Organization'),
            required=True,
            widget=forms.HiddenInput if 'organization' in initial else forms.TextInput
        )
    
        phone_regex = settings.HORIZON_CONFIG.get('phone_regex', '^\s*\+*[0-9]+[0-9\s.]+\s*$')
        self.fields['phone'] = forms.RegexField(
            label=_('Phone number'),
            required=True,
            regex=phone_regex,
            error_messages={'invalid': _("Wrong phone format")}
        )
    
        self.fields['contactper'] = forms.CharField(
            label=_('Contact person'),
            required=False
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

        import_guest_project()
        
        missing_guest = True
        avail_prjs = list()
        for prj_entry in Project.objects.exclude(status=PRJ_PRIVATE):
            if prj_entry.status == PRJ_GUEST:
                missing_guest = False
            elif prj_entry.projectid:
                avail_prjs.append((prj_entry.projectname, prj_entry.projectname))
                
        self.fields['selprj'].choices = avail_prjs
        
        if missing_guest:
            p_choices = [
                ('selprj', _('Select existing projects')),
                ('newprj', _('Create new project'))
            ]
        else:
            p_choices = [
                ('selprj', _('Select existing projects')),
                ('newprj', _('Create new project')),
                ('guestprj', _('Use guest project'))
            ]
            
        self.fields['prjaction'].choices = p_choices


    def clean(self):
        data = super(RegistrForm, self).clean()
        
        if data['prjaction'] == 'newprj':
            if not data['newprj']:
                raise ValidationError(_('Project name is required.'))
        elif data['prjaction'] == 'selprj':
            if not data['selprj']:
                raise ValidationError(_('Missing selected project.'))
        elif data['prjaction'] <> 'guestprj':
            raise ValidationError(_('Wrong project parameter.'))
        
        if data.get('aupok', 'reject') <> 'accept':
            raise ValidationError(_('You must accept Cloud Padovana AUP.'))
            
        if 'pwd' in data and data['pwd'] != data.get('repwd', None):
                raise ValidationError(_('Passwords do not match.'))

        if '@' in data['username'] or ':' in data['username']:
            if data.get('federated', 'false') == 'false':
                raise ValidationError(_("Invalid characters in user name (@:)"))
        
        return data

    def _build_safe_redirect(self, request, location):
        attributes = get_manager(request)
        if attributes:
            safe_loc = attributes.get_logout_url(location)
            response = shortcuts.redirect(safe_loc)
            response = attributes.postproc_logout(response)
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
                    PRJ_PRIVATE if data['prjpriv'] else PRJ_PUBLIC,
                    True
                ))

            LOG.debug("Saving %s" % data['username'])
                    
            with transaction.atomic():
            
                if RegRequest.objects.filter(externalid=data['username']).count():
                    raise ValidationError("Request already sent")
        
                queryArgs = {
                    'username' : data['username'],
                    'givenname' : data['givenname'],
                    'sn' : data['sn'],
                    'organization' : data['organization'],
                    'phone' : data['phone'],
                    'domain' : domain
                }
                registration = Registration(**queryArgs)
                registration.save()
        
                regArgs = {
                    'registration' : registration,
                    'password' : pwd,
                    'email' : data['email'],
                    'contactper' : data['contactper'],
                    'notes' : data['notes']
                }
                if data.get('federated', 'false') == 'true':
                    regArgs['externalid'] = data['username']
                regReq = RegRequest(**regArgs)
                regReq.save()
                
                LOG.debug("Saved %s" % data['username'])

                #
                # empty list for guest prj
                #
                if len(prjlist) == 0:
                    for item in Project.objects.filter(status=PRJ_GUEST):
                        prjlist.append((item.projectname, None, 0, False))

                for prjitem in prjlist:
            
                    if prjitem[3]:

                        prjArgs = {
                            'projectname' : prjitem[0],
                            'description' : prjitem[1],
                            'status' : prjitem[2]
                        }
                        project = Project.objects.create(**prjArgs)

                    else:
                        project = Project.objects.get(projectname=prjitem[0])
            
                    reqArgs = {
                        'registration' : registration,
                        'project' : project,
                        'notes' : data['notes']
                    }
                    
                    reqPrj = PrjRequest(**reqArgs)
                    reqPrj.save()
                
            noti_sbj, noti_body = notification_render(REGISTR_AVAIL_TYPE, {'username' : data['username']})
            notifyManagers(noti_sbj, noti_body)

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



