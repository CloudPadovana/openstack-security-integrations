
from django.conf.urls.defaults import patterns  # noqa
from django.conf.urls.defaults import url  # noqa

from openstack_dashboard.dashboards.admin.user_manager import views


urlpatterns = patterns('openstack_dashboard.dashboards.admin.user_manager.views',
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<user_id>[^/]+)/update/$', views.UpdateView.as_view(), name='update'),
    url(r'^(?P<user_id>[^/]+)/renew/$', views.RenewView.as_view(), name='renew'),
    url(r'^create/$', views.CreateView.as_view(), name='create'))

