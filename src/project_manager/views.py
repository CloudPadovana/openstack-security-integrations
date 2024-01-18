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
import urllib.parse

from django.db import transaction
from django.conf import settings
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from horizon import forms
from horizon import exceptions

from openstack_dashboard.dashboards.identity.projects import views as baseViews
from openstack_dashboard import api

from .forms import CourseForm
from .forms import EditTagsForm
from .forms import CourseDetailForm
from .forms import ProposedRenewForm
from .forms import SubscribeForm
from .tables import ProjectsTable
from .workflows import ExtUpdateProject
from .workflows import ExtCreateProject

from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import PRJ_PRIVATE
from openstack_auth_shib.models import PSTATUS_REG
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.utils import ORG_TAG_FMT
from openstack_auth_shib.utils import TENANTADMIN_ROLE

from openstack_auth_shib.models import NEW_MODEL
if NEW_MODEL:
    from openstack_auth_shib.utils import get_course_info
else:
    from openstack_auth_shib.utils import parse_course_info

from openstack_dashboard.api import keystone as keystone_api

LOG = logging.getLogger(__name__)
baseViews.INDEX_URL = "horizon:idmanager:project_manager:index"

class ExtPrjItem:
    def __init__(self, prj_data):
        self.id = prj_data.id
        self.name = prj_data.name
        self.description = prj_data.description if prj_data.description else ""
        self.enabled = prj_data.enabled
        self.tags = None
        self.status = PRJ_PRIVATE
        self.managed = False
        self.isadmin = False
        self.handle_course = False
        self.flowstatus = PSTATUS_REG

    def items(self):
        return [
            ('id', self.id),
            ('name', self.name),
            ('description', self.description),
            ('enabled', self.enabled),
            ('tags', self.tags),
            ('status', self.status),
            ('managed', self.managed),
            ('isadmin', self.isadmin),
            ('handle_course', self.handle_course),
            ('flowstatus', self.flowstatus)
        ]

class IndexView(baseViews.IndexView):
    table_class = ProjectsTable
    template_name = 'idmanager/project_manager/index.html'

    def get_data(self):

        course_table = settings.HORIZON_CONFIG.get('course_for', {})
    
        result = list()
        try:
            tenants = super(IndexView, self).get_data()
            if len(tenants) == 0:
                return result
            
            prj_table = dict()
            for item in tenants:
                prj_table[item.name] = ExtPrjItem(item)

            kprj_man = keystone_api.keystoneclient(self.request).projects

            with transaction.atomic():

                prj_list = Project.objects.filter(projectname__in=list(prj_table.keys()))

                role_list = PrjRole.objects.filter(
                    registration__userid = self.request.user.id,
                    project__in = prj_list
                )
                for r_item in role_list:
                    prj_table[r_item.project.projectname].isadmin = True

                for prj_item in prj_list:
                    prjname = prj_item.projectname
                    prj_table[prjname].status = prj_item.status
                    prj_table[prjname].managed = True

                    is_curr_admin = self.request.user.tenant_name == prjname
                    is_curr_admin = is_curr_admin and prj_table[prjname].isadmin

                    show_tags = self.request.user.is_superuser and settings.HORIZON_CONFIG.get('show_tags', False)
                    show_tags = show_tags or is_curr_admin

                    if prj_item.projectid and show_tags:
                        prj_table[prjname].tags = set(kprj_man.list_tags(prj_item.projectid))
                    else:
                        prj_table[prjname].tags = set()

                    if is_curr_admin:
                        for item in course_table.keys():
                            if (ORG_TAG_FMT % item) in prj_table[prjname].tags:
                                prj_table[prjname].handle_course = True

                if not self.request.user.is_superuser:
                    preq_list = PrjRequest.objects.filter(
                        registration__userid = self.request.user.id,
                        project__in = prj_list
                    )
                    for req_item in preq_list:
                        prj_table[req_item.project.projectname].flowstatus = req_item.flowstatus

                    qset1 = Expiration.objects.filter(registration__userid = self.request.user.id)
                    for prjname, expdate in qset1.values_list('project', 'expdate'):
                        if prj_table[prjname].flowstatus == PSTATUS_RENEW_ADMIN \
                            or prj_table[prjname].flowstatus == PSTATUS_RENEW_MEMB:
                            prj_table[prjname].expiration = _("Waiting for renewal")
                        else:
                            prj_table[prjname].expiration = expdate


            tmplist = list(prj_table.keys())
            tmplist.sort()
            for item in tmplist:
                result.append(prj_table[item])
            
        except Exception:
            exceptions.handle(self.request, _("Unable to retrieve project list."))
        return result


class UpdateProjectView(baseViews.UpdateProjectView):
    workflow_class = ExtUpdateProject

class CreateProjectView(baseViews.CreateProjectView):
    workflow_class = ExtCreateProject

class ProjectUsageView(baseViews.ProjectUsageView):
    template_name = 'idmanager/project_manager/usage.html'

class DetailProjectView(baseViews.DetailProjectView):
    template_name = 'idmanager/project_manager/detail.html'

    def get_context_data(self, **kwargs):
        context = super(baseViews.DetailProjectView, self).get_context_data(**kwargs)
        project = self.get_data()
        context["project"] = project
        context["url"] = reverse("horizon:idmanager:project_manager:index")

        #context["actions"] = ProjectsTable(self.request).render_row_actions(project)

        if not self.request.user.is_superuser:
            return context

        try:
            kprj_man = keystone_api.keystoneclient(self.request).projects
            context['prj_tags'] = ", ".join(kprj_man.list_tags(project.id))

            with transaction.atomic():
                tmpl = PrjRole.objects.filter(project__projectid = project.id)
                q_list = [ x.registration for x in tmpl ]
                admin_list = [
                    {
                        'id' : x.registration.username,
                        'givenname' : x.registration.givenname,
                        'sn' : x.registration.sn,
                        'email' : x.email
                    }
                    for x in EMail.objects.filter(registration__in = q_list)
                ]
            context['admin_list'] = admin_list
        except:
            LOG.error("Cannot retrieve project details", exc_info=True)

        return context

class CourseView(forms.ModalFormView):
    form_class = CourseForm
    template_name = 'idmanager/project_manager/course.html'
    success_url = reverse_lazy('horizon:idmanager:project_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = Project.objects.filter(projectid=self.kwargs['project_id'])[0]
        return self._object

    def get_context_data(self, **kwargs):
        context = super(CourseView, self).get_context_data(**kwargs)
        context['projectid'] = self.get_object().projectid
        return context

    def get_initial(self):
        if NEW_MODEL:
            course_info = get_course_info(self.get_object().projectname)
        else:
            course_info = parse_course_info(self.get_object().description,
                                            self.get_object().projectname)
        course_info['projectid'] = self.get_object().projectid
        return course_info

class CourseDetailView(forms.ModalFormView):
    form_class = CourseDetailForm
    template_name = 'idmanager/project_manager/course_detail.html'
    success_url = reverse_lazy('horizon:idmanager:project_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = Project.objects.filter(projectid=self.kwargs['project_id'])[0]
        return self._object

    def get_initial(self):

        suffix = "/auth/course_" + urllib.parse.quote(self.get_object().projectname)

        if NEW_MODEL:
            info_table = get_course_info(self.get_object().projectname)
        else:
            info_table = parse_course_info(self.get_object().description,
                                           self.get_object().projectname)

        course_table = settings.HORIZON_CONFIG.get('course_for', {})

        idpref = course_table.get(info_table['org'], None)
        if idpref:
            reg_path = settings.HORIZON_CONFIG['identity_providers'][idpref]['path']
            return { 'courseref': reg_path[0:reg_path.find('dashboard') + 9] + suffix }
        return { 'courseref' : 'https://cloudveneto.ict.unipd.it/dashboard' + suffix }

class EditTagsView(forms.ModalFormView):
    form_class = EditTagsForm
    template_name = 'idmanager/project_manager/edittags.html'
    success_url = reverse_lazy('horizon:idmanager:project_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = Project.objects.filter(projectid=self.kwargs['project_id'])[0]
        return self._object

    def get_context_data(self, **kwargs):
        context = super(EditTagsView, self).get_context_data(**kwargs)
        context['projectname'] = self.get_object().projectname
        context['projectid'] = self.get_object().projectid
        return context

    def get_initial(self):
        result = {
            'projectid' : self.get_object().projectid,
        }

        try:
            kprj_man = keystone_api.keystoneclient(self.request).projects
            init_tags = kprj_man.list_tags(self.kwargs['project_id'])
            result['taglist'] = ", ".join(init_tags)
        except:
            LOG.error("Cannot retrieve tags", exc_info=True)

        return result

class ProposedRenewView(forms.ModalFormView):
    form_class = ProposedRenewForm
    template_name = 'idmanager/project_manager/proposedrenew.html'
    success_url = reverse_lazy('horizon:idmanager:project_manager:index')  # TODO redirect to user home

    def get_context_data(self, **kwargs):
        context = super(ProposedRenewView, self).get_context_data(**kwargs)
        context['project'] = self.request.user.tenant_name

        if self.request.user.has_perms(('openstack.roles.' + TENANTADMIN_ROLE,)):
            q_args = { 'project__projectid' : self.request.user.tenant_id }
            context['unique_admin'] = PrjRole.objects.filter(**q_args).count() == 1
        else:
            context['unique_admin'] = False

        return context

class SubscribeView(forms.ModalFormView):
    form_class = SubscribeForm
    template_name = 'idmanager/project_manager/prj_request.html'
    success_url = reverse_lazy('horizon:idmanager:project_manager:index')

