import logging

from django.db import transaction

from openstack_dashboard.dashboards.admin.projects.workflows import CreateProject as BaseCreateProject
from openstack_dashboard.dashboards.admin.projects.workflows import UpdateProject as BaseUpdateProject

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_PUBLIC

LOG = logging.getLogger(__name__)

class UpdateProject(BaseUpdateProject):
    success_url = "horizon:admin:project_manager:index"

class CreateProject(BaseCreateProject):
    success_url = "horizon:admin:project_manager:index"
    
    def handle(self, request, data):
        
        domain_id = data['domain_id']
        desc = data['description']
        name=data['name']

        #
        # TODO rollback of keystone action
        #
        with transaction.commit_on_success():
        
            super(CreateProject, self).handle(request, data)
            
            qargs = {
                'projectname' : name,
                'projectid' : self.object.id,
                'description' : desc,
                'status' : PRJ_PUBLIC
            }
            newprj = Project(**qargs)
            newprj.save()
            
        return True

