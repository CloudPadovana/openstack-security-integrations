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
from django.utils.translation import ugettext_lazy as _

from horizon import forms
from horizon import workflows

from openstack_dashboard.dashboards.identity.projects.workflows import CreateProject as BaseCreateProject
from openstack_dashboard.dashboards.identity.projects.workflows import UpdateProject as BaseUpdateProject

from openstack_dashboard.dashboards.identity.projects.workflows import CreateProjectInfo
from openstack_dashboard.dashboards.identity.projects.workflows import UpdateProjectMembers
from openstack_dashboard.dashboards.identity.projects.workflows import UpdateProjectGroups
from openstack_dashboard.dashboards.identity.projects.workflows import UpdateProjectQuota
from openstack_dashboard.dashboards.identity.projects.workflows import CreateProjectInfoAction

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_PUBLIC, PRJ_GUEST
from openstack_auth_shib.utils import get_admin_roleid, get_project_managers

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)

class UpdateProject(BaseUpdateProject):
    success_url = "horizon:identity:project_manager:index"
    
    #
    # TODO implement project renaming
    #


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
    contributes = ("domain_id",
                   "domain_name",
                   "project_id",
                   "name",
                   "description",
                   "enabled",
                   "guest")

    

class CreateProject(BaseCreateProject):
    success_url = "horizon:identity:project_manager:index"
    
    def __init__(self, request=None, context_seed=None, entry_point=None, *args, **kwargs):

        self.default_steps = (ExtCreateProjectInfo,
                              UpdateProjectMembers,
                              UpdateProjectGroups,
                              UpdateProjectQuota)

        workflows.Workflow.__init__(self, request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)



    def handle(self, request, data):
        
        domain_id = data['domain_id']
        desc = data['description']
        name=data['name']

        #
        # TODO rollback of keystone action
        #
        with transaction.atomic():
        
            super(CreateProject, self).handle(request, data)
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

