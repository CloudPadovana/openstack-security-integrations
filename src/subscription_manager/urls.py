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
from openstack_dashboard.dashboards.idmanager.subscription_manager import views

index_url = url(r'^$', views.IndexView.as_view(), name='index')
appr_url = url(r'^(?P<regid>[^/]+)/approve/$', views.ApproveView.as_view(), name='approve')
rej_url = url(r'^(?P<regid>[^/]+)/reject/$', views.RejectView.as_view(), name='reject')
ren_url = url(r'^(?P<regid>[^/]+)/renew/$', views.RenewView.as_view(), name='renew')
disc_url = url(r'^(?P<regid>[^/]+)/discard/$', views.DiscardView.as_view(), name='discard')

if django_version[1] < 11:

    from django.conf.urls import patterns

    prefix = 'openstack_dashboard.dashboards.idmanager.subscription_manager.views'

    urlpatterns = patterns(prefix,
                           index_url,
                           appr_url,
                           rej_url,
                           ren_url,
                           disc_url
    )

else:

    urlpatterns = [
        index_url,
        appr_url,
        rej_url,
        ren_url,
        disc_url
    ]

