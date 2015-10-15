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

from django.utils.translation import ugettext_lazy as _

from horizon import exceptions

from openstack_dashboard.dashboards.identity.projects.views import IndexView as BaseIndexView
from openstack_dashboard.dashboards.identity.projects.views import CreateProjectView as BaseCreateProjectView
from openstack_dashboard.dashboards.identity.projects.views import UpdateProjectView as BaseUpdateProjectView
from openstack_dashboard.dashboards.identity.projects.views import ProjectUsageView
from openstack_dashboard import api

from .tables import ProjectsTable
from .workflows import ExtUpdateProject
from .workflows import ExtCreateProject

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_PRIVATE
from openstack_auth_shib.utils import import_guest_project

LOG = logging.getLogger(__name__)

class ExtPrjItem:
    def __init__(self, prj_data):
        self.id = prj_data.id
        self.name = prj_data.name
        self.description = prj_data.description if prj_data.description else ""
        self.enabled = prj_data.enabled
        self.status = PRJ_PRIVATE
        self.checked = False

class IndexView(BaseIndexView):
    table_class = ProjectsTable
    template_name = 'idmanager/project_manager/index.html'

    def get_data(self):
    
        import_guest_project()
        
        result = list()
        try:
            tenants = super(IndexView, self).get_data()
            if len(tenants) == 0:
                return result
            
            prj_table = dict()
            for item in tenants:
                prj_table[item.name] = ExtPrjItem(item)
            
            prj_list = Project.objects.filter(projectname__in=prj_table.keys())
            for prj_item in prj_list:
                prj_table[prj_item.projectname].status = prj_item.status
                prj_table[prj_item.projectname].checked = True
            
            # Auto-import of external projects
            for item in prj_table:
                if not prj_table[item].checked:
                    p_query = {
                        'projectname' : prj_table[item].name,
                        'projectid' : prj_table[item].id,
                        'description' : prj_table[item].description,
                        'status' : PRJ_PRIVATE
                    }
                    imprj = Project(**p_query)
                    imprj.save()
            
            tmplist = prj_table.keys()
            tmplist.sort()
            for item in tmplist:
                result.append(prj_table[item])
            
        except Exception:
            exceptions.handle(self.request, _("Unable to retrieve project list."))
        return result


class UpdateProjectView(BaseUpdateProjectView):
    workflow_class = ExtUpdateProject

class CreateProjectView(BaseCreateProjectView):
    workflow_class = ExtCreateProject

