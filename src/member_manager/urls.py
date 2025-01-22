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
from openstack_dashboard.dashboards.idmanager.member_manager import views

urlpatterns = [
    url(r'^(?P<userid>[^/]+)/modifyexp/$', views.ModifyExpView.as_view(), name='modifyexp'),
    url(r'^(?P<userid>[^/]+)/demote/$', views.DemoteUserView.as_view(), name='demote'),
    url(r'^(?P<userid>[^/]+)/proposeadmin/$', views.ProposeAdminView.as_view(), name='proposeadmin'),
    url(r'^sendmsg/$', views.SendMsgView.as_view(), name='sendmsg'),
    url(r'^$', views.IndexView.as_view(), name='index')
]
