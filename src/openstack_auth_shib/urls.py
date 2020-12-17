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
from openstack_auth_shib import views

from openstack_auth.utils import patch_middleware_get_user
patch_middleware_get_user()

urlpatterns = [
    url(r"^login/$", views.login, name='login'),
    url(r"^authzchk/$", views.authzchk, name='authzchk'),
    url(r"^resetsso/$", views.resetsso, name='resetsso'),
    url(r"^course_(?P<project_name>[^/$]+)/$", views.course, name='course'),
    url(r"^websso/$", views.websso, name='websso'),
    url(r"^logout/$", views.logout, name='logout'),
    url(r'^switch/(?P<tenant_id>[^/]+)/$', views.switch, name='switch_tenants'),
    url(r'^switch_services_region/(?P<region_name>[^/]+)/$', views.switch_region, name='switch_services_region'),
    url(r"^register/$", views.RegistrView.as_view(), name='register'),
    url(r"^reg_done/$", views.reg_done, name='reg_done'),
    url(r"^name_exists/$", views.name_exists, name='name_exists'),
    url(r"^reg_failure/$", views.reg_failure, name='reg_failure'),
    url(r"^dup_login/$", views.dup_login, name='dup_login'),
    url(r"^already_subscribed/$", views.alreay_subscribed, name='dup_subscr'),
    url(r"^auth_error/$", views.auth_error, name='auth_error')
]

