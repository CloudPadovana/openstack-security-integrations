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
from horizon import messages

from django.db import transaction
from django.db import IntegrityError
from django.views.decorators.debug import sensitive_variables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import EMail

from openstack_auth_shib.models import PRJ_PUBLIC,PRJ_PRIVATE
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import OS_SNAME_LEN

from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import notifyProject
from openstack_auth_shib.notifications import NEWPRJ_REQ_TYPE
from openstack_auth_shib.notifications import MEMBER_REQUEST

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ProjectRequestForm(forms.SelfHandlingForm):

    prjaction = forms.ChoiceField(
        label=_('Project action'),
        choices = [
            ('newprj', _('Create new project')),
        ],
        widget=forms.Select(attrs={
            'class': 'switchable',
            'data-slug': 'actsource'
        })
    )
    
    newprj = forms.CharField(
        label=_('Personal project'),
        max_length=OS_SNAME_LEN,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-newprj': _('Project name')
        })
    )
    prjdescr = forms.CharField(
        label=_("Project description"),
        required=False,
        widget=forms.widgets.Textarea(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-newprj': _('Project description')
        })
    )
    prjpriv = forms.BooleanField(
        label=_("Private project"),
        required=False,
        initial=False,
        widget=forms.widgets.CheckboxInput(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-newprj': _('Private project')
        })
    )
    
    selprj = forms.MultipleChoiceField(
        label=_('Available projects'),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-selprj': _('Select existing project')
        }),
    )


    notes = forms.CharField(
        label=_('Notes'),
        required=False,
        widget=forms.widgets.Textarea()
    )

    def __init__(self, *args, **kwargs):
        super(ProjectRequestForm, self).__init__(*args, **kwargs)

        auth_prjs = [
            pitem.name for pitem in self.request.user.authorized_tenants
        ]

        pendPReq = PrjRequest.objects.filter(registration__userid=self.request.user.id)
        self.pendingProjects = [ prjreq.project.projectname for prjreq in pendPReq ]
        excl_prjs = auth_prjs + self.pendingProjects

        prj_list = Project.objects.exclude(projectname__in=excl_prjs)
        prj_list = prj_list.filter(status=PRJ_PUBLIC, projectid__isnull=False)

        prjEntries = [
            (prj_entry.projectname, prj_entry.projectname) for prj_entry in prj_list
        ]
        if len(prjEntries):
            self.fields['selprj'].choices = prjEntries
            self.fields['prjaction'].choices = [
                ('newprj', _('Create new project')),
                ('selprj', _('Select existing projects'))
            ]
        

    @sensitive_variables('data')
    def handle(self, request, data):
    
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
                    PRJ_PRIVATE if data['prjpriv'] else PRJ_PUBLIC,
                    True
                ))

        
            newprjlist = list()
            exstprjlist = list()
            for prjitem in prjlist:
        
                if prjitem[3]:
                    try:

                        prjArgs = {
                            'projectname' : prjitem[0],
                            'description' : prjitem[1],
                            'status' : prjitem[2]
                        }
                        project = Project.objects.create(**prjArgs)
                        newprjlist.append(project.projectname)

                    except IntegrityError:
                        messages.error(request, _("Project %s already exists") % prjitem[0])
                        LOG.error("Cannot create project %s" % prjitem[0])
                        return False
                
                elif prjitem[0] in self.pendingProjects:
                    continue
                else:
                    project = Project.objects.get(projectname=prjitem[0])
                    exstprjlist.append(project)
                        
                reqArgs = {
                    'registration' : registration,
                    'project' : project,
                    'flowstatus' : PSTATUS_PENDING,
                    'notes' : data['notes']
                }                
                reqPrj = PrjRequest(**reqArgs)
                reqPrj.save()

            #
            # Send notification to cloud admins for project creation
            #
            for prj_name in newprjlist:
                noti_params = {
                    'username' : request.user.username,
                    'project' : prj_name
                }
                notifyAdmin(request=self.request, action=NEWPRJ_REQ_TYPE, context=noti_params)

            #
            # Send notifications to project managers
            #
            for prj_item in exstprjlist:

                admin_emails = list()
                for prj_role in PrjRole.objects.filter(project=prj_item):
                    for email_obj in EMail.objects.filter(registration=prj_role.registration):
                        admin_emails.append(email_obj.email)

                noti_params = {
                    'username' : request.user.username,
                    'project' : prj_item.projectname
                }
                notifyProject(request=request, rcpt=admin_emails, action=MEMBER_REQUEST, 
                              context=noti_params)

        return True



