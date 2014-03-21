import logging

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from horizon import forms
from horizon import workflows

from openstack_dashboard.dashboards.admin.projects.workflows import CreateProject as BaseCreateProject
from openstack_dashboard.dashboards.admin.projects.workflows import UpdateProject as BaseUpdateProject

from openstack_dashboard.dashboards.admin.projects.workflows import CreateProjectInfo
from openstack_dashboard.dashboards.admin.projects.workflows import UpdateProjectMembers
from openstack_dashboard.dashboards.admin.projects.workflows import UpdateProjectGroups
from openstack_dashboard.dashboards.admin.projects.workflows import UpdateProjectQuota
from openstack_dashboard.dashboards.admin.projects.workflows import CreateProjectInfoAction

from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PRJ_PUBLIC, PRJ_GUEST

LOG = logging.getLogger(__name__)

class UpdateProject(BaseUpdateProject):
    success_url = "horizon:admin:project_manager:index"


class ExtCreateProjectInfoAction(CreateProjectInfoAction):

    guest = forms.BooleanField(
        label=_("Guest Project"),
        required=False,
        initial=False
    )


    def __init__(self, request, *args, **kwargs):
        super(ExtCreateProjectInfoAction, self).__init__(request, *args, **kwargs)

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
    success_url = "horizon:admin:project_manager:index"
    
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
        with transaction.commit_on_success():
        
            is_guest = False
            if data['guest']:
                is_guest = (Project.objects.filter(status=PRJ_GUEST).count() == 0)
        
            super(CreateProject, self).handle(request, data)
            
            qargs = {
                'projectname' : name,
                'projectid' : self.object.id,
                'description' : desc,
                'status' : PRJ_GUEST if is_guest else PRJ_PUBLIC
            }
            newprj = Project(**qargs)
            newprj.save()
            
        return True

