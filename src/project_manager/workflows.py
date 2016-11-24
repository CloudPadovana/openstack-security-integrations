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
from django.db import IntegrityError
from django.utils.translation import ugettext_lazy as _

from horizon import forms
from horizon import workflows

from openstack_dashboard.dashboards.identity.projects import workflows as baseWorkflows

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import PRJ_PUBLIC
from openstack_auth_shib.models import PRJ_GUEST
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.utils import TENANTADMIN_ROLE

LOG = logging.getLogger(__name__)
#
# Inject new urls in parent fields
#
baseWorkflows.INDEX_URL = "horizon:idmanager:project_manager:index"
baseWorkflows.ADD_USER_URL = "horizon:idmanager:project_manager:create_user"

class ExtCreateProjectInfoAction(baseWorkflows.CreateProjectInfoAction):

    def __init__(self, request, *args, **kwargs):
        super(ExtCreateProjectInfoAction, self).__init__(request, *args, **kwargs)
        
        if Project.objects.filter(status=PRJ_GUEST).count() == 0:
            self.fields['guest'] = forms.BooleanField(
                label=_("Guest Project"),
                required=False,
                initial=False
            )

    class Meta:
        name = _("Project Info")
        help_text = _("From here you can create a new "
                      "project to organize users.")


class ExtCreateProjectInfo(baseWorkflows.CreateProjectInfo):
    action_class = ExtCreateProjectInfoAction
    template_name = "idmanager/project_manager/_common_horizontal_form.html"
    contributes = ("domain_id",
                   "domain_name",
                   "project_id",
                   "name",
                   "description",
                   "enabled",
                   "guest")

class ExtCreateProjectQuota(baseWorkflows.CreateProjectQuota):
    template_name = "idmanager/project_manager/_common_horizontal_form.html"

class ExtCreateProject(baseWorkflows.CreateProject):
    success_url = "horizon:idmanager:project_manager:index"
    
    def __init__(self, request=None, context_seed=None, entry_point=None, *args, **kwargs):

        self.default_steps = (ExtCreateProjectInfo,
                              baseWorkflows.UpdateProjectMembers,
                              baseWorkflows.UpdateProjectGroups,
                              ExtCreateProjectQuota)

        workflows.Workflow.__init__(self, request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)
        self.this_project = None

    def _update_project_members(self, request, data, project_id):
        #
        # Use per-user expiration date as a fall back
        # for expiration date per tenant
        #
        
        admin_role_id = None
        missing_admin = True
        available_roles = baseWorkflows.api.keystone.role_list(request)
        
        with transaction.atomic():

            for role in available_roles:
            
                tmp_step = self.get_step(baseWorkflows.PROJECT_USER_MEMBER_SLUG)
                field_name = tmp_step.get_member_field_name(role.id)

                if role.name == TENANTADMIN_ROLE:
                    admin_role_id = role.id
                    missing_admin = (len(data[field_name]) == 0)

                for user_id in data[field_name]:
                    q_args = {
                        'userid' : user_id,
                        'expdate__isnull' : False
                    }
                    tmp_list = Registration.objects.filter(**q_args)

                    if len(tmp_list):
                        q_args = {
                            'registration' : tmp_list[0],
                            'project' : self.this_project
                        }
                        if not Expiration.objects.filter(**q_args).count():
                            c_args = {
                                'registration' : tmp_list[0],
                                'project' : self.this_project,
                                'expdate' : tmp_list[0].expdate
                            }
                            Expiration(**c_args).save()

            #
            # Insert cloud admin as project_manager if missing
            # No tenant admin for guest
            #
            if missing_admin and not data.get('guest', False):
                baseWorkflows.api.keystone.add_tenant_user_role(request, project_id,
                                                    request.user.id, admin_role_id)

        #
        # TODO if this is the guest project don't define any tenant admin
        #
        return super(ExtCreateProject, self)._update_project_members(request, data, project_id)

    def _create_project(self, request, data):
        
        result = super(ExtCreateProject, self)._create_project(request, data)
        if not result:
            return None
        
        with transaction.atomic():
        
            newprj_id = self.object.id
            
            qargs = {
                'projectname' : data['name'],
                'projectid' : newprj_id,
                'description' : data['description'],
                'status' : PRJ_GUEST if data.get('guest', False) else PRJ_PUBLIC
            }
            newprj = Project(**qargs)
            newprj.save()
            self.this_project = newprj
                    
        return result

class ExtUpdateProjectInfo(baseWorkflows.UpdateProjectInfo):
    template_name = "idmanager/project_manager/_common_horizontal_form.html"

class ExtUpdateProjectQuota(baseWorkflows.UpdateProjectQuota):
    template_name = "idmanager/project_manager/_common_horizontal_form.html"

class ExtUpdateProject(baseWorkflows.UpdateProject):
    success_url = "horizon:idmanager:project_manager:index"
    
    def __init__(self, request=None, context_seed=None, entry_point=None, *args, **kwargs):

        self.default_steps = (ExtUpdateProjectInfo,
                              baseWorkflows.UpdateProjectMembers,
                              baseWorkflows.UpdateProjectGroups,
                              ExtUpdateProjectQuota)

        workflows.Workflow.__init__(self,request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)
        self.this_project = None

    def _update_project_members(self, request, data, project_id):
        #
        # Use per-user expiration date as a fall back
        # for expiration date per tenant
        #
        # Remove subscription request for this project
        #
        for role in self._get_available_roles(request):

            tmp_step = self.get_step(baseWorkflows.PROJECT_USER_MEMBER_SLUG)
            field_name = tmp_step.get_member_field_name(role.id)

            with transaction.atomic():
                for user_id in data[field_name]:
                    q_args = {
                        'userid' : user_id,
                        'expdate__isnull' : False
                    }
                    tmp_list = Registration.objects.filter(**q_args)
                    if len(tmp_list):
                        q_args = {
                            'registration' : tmp_list[0],
                            'project' : self.this_project
                        }
                        if not Expiration.objects.filter(**q_args).count():
                            c_args = {
                                'registration' : tmp_list[0],
                                'project' : self.this_project,
                                'expdate' : tmp_list[0].expdate
                            }
                            Expiration(**c_args).save()

                    q_args = {
                        'registration' : tmp_list[0],
                        'project' : self.this_project,
                        'flowstatus' : PSTATUS_PENDING
                    }
                    PrjRequest.objects.filter(**q_args).delete()
                        

        return super(ExtUpdateProject, self)._update_project_members(request, data, project_id)

    def handle(self, request, data):

        new_name=data['name']
        new_desc = data['description']
        project_id = data['project_id']

        with transaction.atomic():
            #
            # TODO missing index
            #
            pr_list = Project.objects.filter(projectid=project_id)
            
            if len(pr_list) == 0:
                LOG.error("Missing project %s in database" % project_id)
                return False
            else:
                self.this_project = pr_list[0]

            if new_name == self.this_project.projectname:
                #
                # Change project description
                #
                self.this_project.description = new_desc
                self.this_project.save()
            else:
                #
                # Change project name and description
                #
                newpr = Project()
                newpr.projectname = new_name
                newpr.projectid = project_id
                newpr.description = new_desc
                newpr.status = self.this_project.status
                newpr.save()
            
                PrjRequest.objects.filter(project=self.this_project).update(project=newpr)
                Expiration.objects.filter(project=self.this_project).update(project=newpr)
                self.this_project.delete()
                self.this_project = newpr
            
            if not super(ExtUpdateProject, self).handle(request, data):
                raise IntegrityError('Cannot complete update on Keystone')

        return True



