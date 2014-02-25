from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url

from openstack_dashboard.dashboards.settings.password_manager import views


urlpatterns = patterns('openstack_dashboard.dashboards.settings.password_manager.views',
    url(r'^$', views.PasswordView.as_view(), name='index'))

