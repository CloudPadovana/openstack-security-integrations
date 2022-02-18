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

from django.conf.urls import url

from openstack_dashboard.dashboards.project.api_access import views as baseViews
from openstack_dashboard.dashboards.project.api_access_manager import views

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^ec2/$', baseViews.download_ec2_bundle, name='ec2'),
    url(r'^clouds.yaml/$',
        baseViews.download_clouds_yaml_file, name='clouds.yaml'),
    url(r'^openrc/$', baseViews.download_rc_file, name='openrc'),
    url(r'^ostoken/$', views.download_os_token_file, name='ostoken'),
    url(r'^view_credentials/$', baseViews.CredentialsView.as_view(),
        name='view_credentials'),
    url(r'^recreate_ec2_credentials/$',
        baseViews.RecreateCredentialsView.as_view(), name='recreate_credentials'),
]

