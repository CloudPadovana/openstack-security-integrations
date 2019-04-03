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


from django import VERSION as django_version
from django.conf.urls import url
from openstack_dashboard.dashboards.idmanager.project_manager import views
from openstack_dashboard.dashboards.identity.projects import views as baseViews

index_url = url(r'^$', views.IndexView.as_view(), name='index')
create_url = url(r'^create$', views.CreateProjectView.as_view(), name='create')
mod_url = url(r'^(?P<tenant_id>[^/]+)/update/$',
        views.UpdateProjectView.as_view(), name='update')
use_url = url(r'^(?P<tenant_id>[^/]+)/usage/$',
        views.ProjectUsageView.as_view(), name='usage')
detail_url = url(r'^(?P<project_id>[^/]+)/detail/$',
        views.DetailProjectView.as_view(), name='detail')
quota_url = url(r'^(?P<tenant_id>[^/]+)/update_quotas/$',
        baseViews.UpdateQuotasView.as_view(), name='update_quotas')
course_url = url(r'^(?P<project_id>[^/]+)/course/$',
        views.CourseView.as_view(), name='course')

if django_version[1] < 11:

    from django.conf.urls import patterns

    urlpatterns = patterns('',
        index_url,
        create_url,
        mod_url,
        use_url,
        detail_url,
        quota_url,
        course_url,
    )

else:

    urlpatterns = [
        index_url,
        create_url,
        mod_url,
        use_url,
        detail_url,
        quota_url,
        course_url
    ]


