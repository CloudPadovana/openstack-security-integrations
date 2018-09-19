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

from datetime import datetime, timedelta

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
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PRJ_PUBLIC
from openstack_auth_shib.models import PRJ_GUEST
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.utils import TENANTADMIN_ROLE

from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import MEMBER_FORCED_ADD
from openstack_auth_shib.notifications import MEMBER_FORCED_RM
from openstack_auth_shib.notifications import NEWPRJ_BY_ADM

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

class ExtCreateProject(baseWorkflows.CreateProject):
    success_url = "horizon:idmanager:project_manager:index"
    
    def __init__(self, request=None, context_seed=None, entry_point=None, *args, **kwargs):

        self.default_steps = (ExtCreateProjectInfo,
                              baseWorkflows.UpdateProjectMembers,
                              baseWorkflows.UpdateProjectGroups)

        workflows.Workflow.__init__(self, request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)
        self.this_project = None

    def _update_project_members(self, request, data, project_id):
        
        admin_role_id = None
        available_roles = baseWorkflows.api.keystone.role_list(request)
        member_ids = set()
        prjadm_ids = set()
        result = None
        
        with transaction.atomic():

            #
            # Create project in the database
            #
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

            #
            # Setup members
            #
            for role in available_roles:
            
                tmp_step = self.get_step(baseWorkflows.PROJECT_USER_MEMBER_SLUG)
                field_name = tmp_step.get_member_field_name(role.id)

                if role.name == TENANTADMIN_ROLE:
                    admin_role_id = role.id
                    for tmpid in data[field_name]:
                        prjadm_ids.add(tmpid)

                for user_id in data[field_name]:
                    member_ids.add(user_id)


            #
            # Import expiration per tenant, use per-user expiration date as a fall back
            # Create the project admin cache
            #
            for u_item in Registration.objects.filter(userid__in=member_ids):

                new_p_exp = Expiration()
                new_p_exp.registration = u_item
                new_p_exp.project = self.this_project
                new_p_exp.expdate = u_item.expdate
                new_p_exp.save()

                if u_item.userid in prjadm_ids:
                    new_prjrole = PrjRole()
                    new_prjrole.registration = u_item
                    new_prjrole.project = self.this_project
                    new_prjrole.roleid = admin_role_id
                    new_prjrole.save()
                    LOG.debug("Created prj admin: %s" % u_item.username)

            #
            # Insert cloud admin as project_manager if missing
            # No tenant admin for guest
            #
            if len(prjadm_ids) == 0 and not data.get('guest', False):
                baseWorkflows.api.keystone.add_tenant_user_role(request, project_id,
                                                    request.user.id, admin_role_id)

            result = super(ExtCreateProject, self)._update_project_members(request, data, project_id)

        #
        # Notify users
        #
        for e_item in EMail.objects.filter(registration__userid__in=member_ids):
            noti_params = {
                'username' : e_item.registration.username,
                'project' : self.this_project.projectname,
                'isadmin' : e_item.registration.userid in prjadm_ids
            }
            notifyUser(request=request, rcpt=e_item.email, action=MEMBER_FORCED_ADD, context=noti_params,
                       dst_project_id=self.this_project.projectid, dst_user_id=e_item.registration.userid)

        #
        # Notify all cloud admins
        #
        notifyAdmin(request=request, action=NEWPRJ_BY_ADM,
                    context={'project' : self.this_project.projectname})        

        return result

class ExtUpdateProjectInfo(baseWorkflows.UpdateProjectInfo):
    template_name = "idmanager/project_manager/_common_horizontal_form.html"

class ExtUpdateProject(baseWorkflows.UpdateProject):
    success_url = "horizon:idmanager:project_manager:index"
    
    def __init__(self, request=None, context_seed=None, entry_point=None, *args, **kwargs):

        self.default_steps = (ExtUpdateProjectInfo,
                              baseWorkflows.UpdateProjectMembers,
                              baseWorkflows.UpdateProjectGroups)

        workflows.Workflow.__init__(self,request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)
        self.this_project = None

    def _update_project_members(self, request, data, project_id):

        member_ids = set()
        prjadm_ids = set()
        prjrole_id = None
        result = None

        for role in self._get_available_roles(request):
            tmp_step = self.get_step(baseWorkflows.PROJECT_USER_MEMBER_SLUG)
            field_name = tmp_step.get_member_field_name(role.id)
            for tmpid in data[field_name]:
                member_ids.add(tmpid)
                if role.name == TENANTADMIN_ROLE:
                    prjadm_ids.add(tmpid)

            if role.name == TENANTADMIN_ROLE:
                prjrole_id = role.id

        with transaction.atomic():
        
            ep_qset = Expiration.objects.filter(project=self.this_project)
        
            #
            # Delete expiration for manually removed users
            #
            tmpl = ep_qset.exclude(registration__userid__in=member_ids)

            rm_email_list = EMail.objects.filter(registration__in=[ x.registration for x in tmpl ])

            tmpl.delete()

            for item in ep_qset:
                if item.registration.userid in member_ids:
                    member_ids.remove(item.registration.userid)

            nreg_qset = Registration.objects.filter(userid__in=member_ids)

            add_email_list = EMail.objects.filter(registration__in=nreg_qset)

            #
            # Use per-user expiration date as a fall back
            # for expiration date per tenant
            #
            for item in nreg_qset:

                def_expdate = item.expdate if item.expdate else datetime.now() + timedelta(365)
                c_args = {
                    'registration' : item,
                    'project' : self.this_project,
                    'expdate' : item.expdate
                }
                Expiration(**c_args).save()
        
            #
            # Remove subscription request for manually added members
            #    
            q_args = {
                'registration__in' : nreg_qset,
                'project' : self.this_project,
                'flowstatus' : PSTATUS_PENDING
            }
            PrjRequest.objects.filter(**q_args).delete()

            #
            # Delete and re-create the project admin cache
            #
            PrjRole.objects.filter(project=self.this_project).delete()
            for item in Registration.objects.filter(userid__in=prjadm_ids):
                new_prjrole = PrjRole()
                new_prjrole.registration = item
                new_prjrole.project = self.this_project
                new_prjrole.roleid = prjrole_id
                new_prjrole.save()
                LOG.debug("Re-created prj admin: %s" % item.username)

            result = super(ExtUpdateProject, self)._update_project_members(request, data, project_id)

        #
        # Notify users, both new and removed
        #
        for e_item in rm_email_list:
            noti_params = {
                'username' : e_item.registration.username,
                'project' : self.this_project.projectname
            }
            notifyUser(request=request, rcpt=e_item.email, action=MEMBER_FORCED_RM, context=noti_params,
                       dst_project_id=self.this_project.projectid, dst_user_id=e_item.registration.userid)

        for e_item in add_email_list:
            noti_params = {
                'username' : e_item.registration.username,
                'project' : self.this_project.projectname,
                'isadmin' : e_item.registration.userid in prjadm_ids
            }
            notifyUser(request=request, rcpt=e_item.email, action=MEMBER_FORCED_ADD, context=noti_params,
                       dst_project_id=self.this_project.projectid, dst_user_id=e_item.registration.userid)

        return result

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



