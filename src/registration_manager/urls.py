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
from openstack_dashboard.dashboards.idmanager.registration_manager import views

urlpatterns = [
    url(r'^$', views.MainView.as_view(), name='index'),
    url(r'^(?P<requestid>[^/]+)/precheck/$', views.PreCheckView.as_view(), name='precheck'),
    url(r'^(?P<requestid>[^/]+)/grantall/$', views.GrantAllView.as_view(), name='grantall'),
    url(r'^(?P<requestid>[^/]+)/reject/$', views.RejectView.as_view(), name='reject'),
    url(r'^(?P<requestid>[^/]+)/details/$', views.DetailsView.as_view(), name='details'),
    url(r'^(?P<requestid>[^/]+)/reminderack/$', views.RemainderAckView.as_view(), 
        name='remainderack'),
    url(r'^(?P<requestid>[^/]+)/compack/$', views.CompAckView.as_view(), 
        name='compack'),
    url(r'^(?P<requestid>[^/]+)/promoteadmin/$', views.PromoteAdminView.as_view(), 
        name='promoteadmin'),
    url(r'^(?P<requestid>[^/]+)/rejectpromotion/$', views.RejectPromotionView.as_view(), 
        name='rejectpromotion'),
    url(r'^(?P<requestid>[^/]+)/forcedapprove/$', views.ForcedApproveView.as_view(), 
        name='forcedapprove'),
    url(r'^(?P<requestid>[^/]+)/forcedreject/$', views.ForcedRejectView.as_view(), 
        name='forcedreject'),
    url(r'^(?P<requestid>[^/]+)/newproject/$', views.NewProjectView.as_view(), 
        name='newproject'),
    url(r'^(?P<requestid>[^/]+)/rejectproject/$', views.RejectProjectView.as_view(), 
        name='rejectproject'),
    url(r'^(?P<requestid>[^/]+)/renewadmin/$', views.RenewAdminView.as_view(), 
        name='renewadmin'),
    url(r'^(?P<requestid>[^/]+)/forcedrenew/$', views.ForcedRenewView.as_view(), 
        name='forcedrenew')
]

