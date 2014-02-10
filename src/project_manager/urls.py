
from django.conf.urls.defaults import patterns  # noqa
from django.conf.urls.defaults import url  # noqa

from openstack_dashboard.dashboards.admin.project_manager import views


urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^create$', views.CreateProjectView.as_view(), name='create'),
    url(r'^(?P<tenant_id>[^/]+)/update/$',
        views.UpdateProjectView.as_view(), name='update'),
    url(r'^(?P<tenant_id>[^/]+)/usage/$',
        views.ProjectUsageView.as_view(), name='usage'),
)

