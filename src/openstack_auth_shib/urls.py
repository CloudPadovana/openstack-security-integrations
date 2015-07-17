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

try:
    from django.conf.urls import patterns, url
except:
    from django.conf.urls.defaults import patterns, url

from openstack_auth.utils import patch_middleware_get_user

patch_middleware_get_user()


urlpatterns = patterns('openstack_auth_shib.views',
    url(r"^login/$", "login", name='login'),
    url(r"^logout/$", 'logout', name='logout'),
    url(r'^switch/(?P<tenant_id>[^/]+)/$', 'switch', name='switch_tenants'),
    url(r'^switch_services_region/(?P<region_name>[^/]+)/$', 'switch_region',
        name='switch_services_region'),
    url(r"^register/$", "register", name='register'),
    url(r"^reg_done/$", "reg_done", name='reg_done'),
    url(r"^name_exists/$", "name_exists", name='name_exists'),
    url(r"^reg_failure/$", "reg_failure", name='reg_failure'),
    url(r"^dup_login/$", "dup_login", name='dup_login'),
    url(r"^auth_error/$", "auth_error", name='auth_error')
)
