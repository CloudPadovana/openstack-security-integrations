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

#
# This is the entry point for the dashboard
# in /usr/share/openstack-dashboard/openstack_dashboard/urls.py
# it is necessary to register:
# url(r'^auth/', include('openstack_auth_shib.urls'))
# instead of
# url(r'^auth/', include('openstack_auth.urls'))
#

from django import VERSION as django_version
from django.conf.urls import url
from openstack_auth.utils import patch_middleware_get_user
from openstack_auth_shib import views

patch_middleware_get_user()

login_url = url(r"^login/$", views.login, name='login')
websso_url = url(r"^websso/$", views.websso, name='websso')
logout_url = url(r"^logout/$", views.logout, name='logout')
switch_url = url(r'^switch/(?P<tenant_id>[^/]+)/$', views.switch, name='switch_tenants')
sw_reg_url = url(r'^switch_services_region/(?P<region_name>[^/]+)/$', views.switch_region,
                 name='switch_services_region')
regis_url = url(r"^register/$", views.RegistrView.as_view(), name='register')
reg_ok_url = url(r"^reg_done/$", views.reg_done, name='reg_done')
namex_url = url(r"^name_exists/$", views.name_exists, name='name_exists')
fail_url = url(r"^reg_failure/$", views.reg_failure, name='reg_failure')
dup_url = url(r"^dup_login/$", views.dup_login, name='dup_login')
err_url = url(r"^auth_error/$", views.auth_error, name='auth_error')
course_url = url(r"^course_(?P<project_name>[^/$]+)/$", views.course, name='course')

if django_version[1] < 11:

    from django.conf.urls import patterns

    urlpatterns = patterns('openstack_auth_shib.views',
                           login_url,
                           course_url,
                           websso_url,
                           logout_url,
                           switch_url,
                           sw_reg_url,
                           regis_url,
                           reg_ok_url,
                           namex_url,
                           fail_url,
                           dup_url,
                           err_url
    )

else:

    urlpatterns = [
        login_url,
        course_url,
        websso_url,
        logout_url,
        switch_url,
        sw_reg_url,
        regis_url,
        reg_ok_url,
        namex_url,
        fail_url,
        dup_url,
        err_url
    ]

