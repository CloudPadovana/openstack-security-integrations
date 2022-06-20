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


from django.urls import re_path as url
from openstack_dashboard.dashboards.idmanager.project_manager import views
from openstack_dashboard.dashboards.identity.projects import views as baseViews

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^create$', views.CreateProjectView.as_view(), name='create'),
    url(r'^(?P<tenant_id>[^/]+)/update/$',
        views.UpdateProjectView.as_view(), name='update'),
    url(r'^(?P<tenant_id>[^/]+)/usage/$',
        views.ProjectUsageView.as_view(), name='usage'),
    url(r'^(?P<project_id>[^/]+)/detail/$',
        views.DetailProjectView.as_view(), name='detail'),
    url(r'^(?P<tenant_id>[^/]+)/update_quotas/$',
        baseViews.UpdateQuotasView.as_view(), name='update_quotas'),
    url(r'^(?P<project_id>[^/]+)/course/$',
        views.CourseView.as_view(), name='course'),
    url(r'^(?P<project_id>[^/]+)/course_detail/$',
        views.CourseDetailView.as_view(), name='course_detail'),
    url(r'^(?P<project_id>[^/]+)/edittags/$',
        views.EditTagsView.as_view(), name='edittags'),
    url(r'^proposedrenew/$',
        views.ProposedRenewView.as_view(), name='proposedrenew')
]


