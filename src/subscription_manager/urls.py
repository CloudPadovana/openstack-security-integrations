from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url

from openstack_dashboard.dashboards.project.subscription_manager import views

prefix = 'openstack_dashboard.dashboards.project.subscription_manager.views'

urlpatterns = patterns(prefix,
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<regid>[^/]+)/approve/$', views.ApproveView.as_view(), name='approve'))

