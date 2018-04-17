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
from openstack_dashboard.dashboards.idmanager.registration_manager import views

index_url = url(r'^$', views.MainView.as_view(), name='index')
prechk_url = url(r'^(?P<requestid>[^/]+)/precheck/$', views.PreCheckView.as_view(), name='precheck')
grant_url = url(r'^(?P<requestid>[^/]+)/grantall/$', views.GrantAllView.as_view(), name='grantall')
rej_url = url(r'^(?P<requestid>[^/]+)/reject/$', views.RejectView.as_view(), name='reject')
detail_url = url(r'^(?P<requestid>[^/]+)/details/$', views.DetailsView.as_view(), name='details')
f_app_url = url(r'^(?P<requestid>[^/]+)/forcedapprove/$', views.ForcedApproveView.as_view(), 
        name='forcedapprove')
f_rej_url = url(r'^(?P<requestid>[^/]+)/forcedreject/$', views.ForcedRejectView.as_view(), 
        name='forcedreject')
newprj_url = url(r'^(?P<requestid>[^/]+)/newproject/$', views.NewProjectView.as_view(), 
        name='newproject')
rejprj_url = url(r'^(?P<requestid>[^/]+)/rejectproject/$', views.RejectProjectView.as_view(), 
        name='rejectproject')
guest_url = url(r'^(?P<requestid>[^/]+)/guestapprove/$', views.GuestApproveView.as_view(), 
        name='guestapprove')
renadm_url = url(r'^(?P<requestid>[^/]+)/renewadmin/$', views.RenewAdminView.as_view(), 
        name='renewadmin')
f_renew_url = url(r'^(?P<requestid>[^/]+)/forcedrenew/$', views.ForcedRenewView.as_view(), 
        name='forcedrenew')

if django_version[1] < 11:

    from django.conf.urls import patterns

    prefix = 'openstack_dashboard.dashboards.idmanager.registration_manager.views'

    urlpatterns = patterns(prefix,
                           index_url,
                           prechk_url,
                           grant_url,
                           rej_url,
                           detail_url,
                           f_app_url,
                           f_rej_url,
                           newprj_url,
                           rejprj_url,
                           guest_url,
                           renadm_url,
                           f_renew_url
        )

else:

    urlpatterns = [
        index_url,
        prechk_url,
        grant_url,
        rej_url,
        detail_url,
        f_app_url,
        f_rej_url,
        newprj_url,
        rejprj_url,
        guest_url,
        renadm_url,
        f_renew_url
    ]

