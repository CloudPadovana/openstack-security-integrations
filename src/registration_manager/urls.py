from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url

from openstack_dashboard.dashboards.admin.registration_manager import views

urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), name='index'))

