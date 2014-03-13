from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url

from openstack_dashboard.dashboards.project.project_requests import views

prefix = 'openstack_dashboard.dashboards.project.project_requests.views'

urlpatterns = patterns(prefix,
    url(r'^$', views.RequestView.as_view(), name='index'))

