from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url

from openstack_dashboard.dashboards.admin.registration_manager import views

prefix = 'openstack_dashboard.dashboards.admin.registration_manager.views'

urlpatterns = patterns(prefix,
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<reqid>[^/]+)/approve/$', views.ApproveView.as_view(), name='approve'))

