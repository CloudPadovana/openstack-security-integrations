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

from openstack_dashboard.dashboards.identity.projects.workflows import *
from openstack_dashboard.dashboards.identity.projects import workflows as baseWorkflows

from openstack_auth_shib.models import Project, PrjRequest
from openstack_auth_shib.models import PRJ_PUBLIC, PRJ_GUEST
from openstack_auth_shib.utils import get_admin_roleid, get_project_managers

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)
baseWorkflows.INDEX_URL = "horizon:idmanager:project_manager:index"
baseWorkflows.ADD_USER_URL = "horizon:idmanager:project_manager:create_user"

class ExtCreateProjectInfoAction(CreateProjectInfoAction):

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


class ExtCreateProjectInfo(CreateProjectInfo):
    action_class = ExtCreateProjectInfoAction
    template_name = "idmanager/project_manager/_common_horizontal_form.html"
    contributes = ("domain_id",
                   "domain_name",
                   "project_id",
                   "name",
                   "description",
                   "enabled",
                   "guest")

class ExtCreateProjectQuota(CreateProjectQuota):
    template_name = "idmanager/project_manager/_common_horizontal_form.html"

class ExtCreateProject(CreateProject):
    success_url = "horizon:idmanager:project_manager:index"
    
    def __init__(self, request=None, context_seed=None, entry_point=None, *args, **kwargs):

        self.default_steps = (ExtCreateProjectInfo,
                              UpdateProjectMembers,
                              UpdateProjectGroups,
                              ExtCreateProjectQuota)

        workflows.Workflow.__init__(self, request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)



    def handle(self, request, data):
        
        name=data['name']
        desc = data['description']
        
        if not super(ExtCreateProject, self).handle(request, data):
            return False

        with transaction.atomic():
        
            newprj_id = self.object.id
            
            qargs = {
                'projectname' : name,
                'projectid' : newprj_id,
                'description' : desc,
                'status' : PRJ_GUEST if data.get('guest', False) else PRJ_PUBLIC
            }
            newprj = Project(**qargs)
            newprj.save()
        
        if data.get('guest', False):
            return True
        
        #
        # Insert admin as project_manager for manually created tenants
        #
        prj_man_list = get_project_managers(request, newprj_id)
        if len(prj_man_list) == 0:
            keystone_api.add_tenant_user_role(request, newprj_id,
                request.user.id, get_admin_roleid(request))
            
        return True

class ExtUpdateProjectInfo(UpdateProjectInfo):
    template_name = "idmanager/project_manager/_common_horizontal_form.html"

class ExtUpdateProjectQuota(UpdateProjectQuota):
    template_name = "idmanager/project_manager/_common_horizontal_form.html"

class ExtUpdateProject(UpdateProject):
    success_url = "horizon:idmanager:project_manager:index"
    
    def __init__(self, request=None, context_seed=None, entry_point=None, *args, **kwargs):

        self.default_steps = (ExtUpdateProjectInfo,
                              UpdateProjectMembers,
                              UpdateProjectGroups,
                              ExtUpdateProjectQuota)

        workflows.Workflow.__init__(self,request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)

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

            if new_name == pr_list[0].projectname:
                pr_list[0].description = new_desc
                pr_list[0].save()
            else:
                newpr = Project()
                newpr.projectname = new_name
                newpr.projectid = project_id
                newpr.description = new_desc
                newpr.status = pr_list[0].status
                newpr.save()
            
                PrjRequest.objects.filter(project=pr_list[0]).update(project=newpr)
                pr_list[0].delete()
            
            if not super(ExtUpdateProject, self).handle(request, data):
                raise IntegrityError('Cannot complete update on Keystone')

        return True



