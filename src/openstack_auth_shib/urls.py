#
# This is the entry point for the dashboard
# in /usr/share/openstack-dashboard/openstack_dashboard/urls.py
# it is necessary to register:
# url(r'^auth/', include('openstack_auth_shib.urls'))
# instead of
# url(r'^auth/', include('openstack_auth.urls'))
#


from django.conf.urls.defaults import patterns, url

from openstack_auth.utils import patch_middleware_get_user

patch_middleware_get_user()


urlpatterns = patterns('openstack_auth_shib.views',
    url(r"^login/$", "login", name='login'),
    url(r"^logout/$", 'logout', name='logout'),
    url(r'^switch/(?P<tenant_id>[^/]+)/$', 'switch', name='switch_tenants'),
    url(r'^switch_services_region/(?P<region_name>[^/]+)/$', 'switch_region',
        name='switch_services_region')
)
