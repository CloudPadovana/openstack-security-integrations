import logging

from threading import Thread

from django import shortcuts
from django.conf import settings
from django.http import HttpResponseForbidden
from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate, login as auth_login

from django.contrib.auth.decorators import login_required
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from openstack_auth.views import login as basic_login
from openstack_auth.views import logout as basic_logout
from openstack_auth.views import switch as basic_switch
from openstack_auth.views import switch_region as basic_switch_region
from openstack_auth.views import delete_all_tokens
from openstack_auth.user import set_session_from_user

LOG = logging.getLogger(__name__)

# TODO
# verify whether it is possible to use just the parent views
# together with the extended backend
# issue: shibboleth redirect converts POST in GET
#        input parameters are lost

@sensitive_post_parameters()
@csrf_protect
@never_cache
def login(request):

    try:
        if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-shib'):

            username = request.META['REMOTE_USER']
            region = getattr(settings, 'OPENSTACK_KEYSTONE_URL').replace('v2.0','v3')
            # TODO
            # retrieve domain from IdP
            domain = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN', 'Default')

            user = authenticate(request=request,
                                username=username,
                                password=None,
                                user_domain_name=domain,
                                auth_url=region)

            auth_login(request, user)
            if request.user.is_authenticated():
                set_session_from_user(request, request.user)
                
                default_region = (settings.OPENSTACK_KEYSTONE_URL, "Default Region")
                regions = dict(getattr(settings, 'AVAILABLE_REGIONS', [default_region]))
                
                region = request.user.endpoint
                region_name = regions.get(region)
                request.session['region_endpoint'] = region
                request.session['region_name'] = region_name
            return shortcuts.redirect( '/dashboard-shib/project' )
            
    except:
        import sys, traceback
        etype, evalue, etraceback = sys.exc_info()
        errmsg = traceback.format_exc(etraceback)
        return HttpResponseForbidden("%s %s" %(evalue, errmsg))
        
    return basic_login(request)


def logout(request):
    if request.path.startswith('/dashboard-shib'):
        msg = 'Logging out user "%(username)s".' % {'username': request.user.username}
        LOG.info(msg)
        if 'token_list' in request.session:
            t = Thread(target=delete_all_tokens,
                   args=(list(request.session['token_list']),))
            t.start()
        return shortcuts.redirect('/Shibboleth.sso/Logout')
    else:
        return basic_logout(request)


@login_required
def switch(request, tenant_id, redirect_field_name=REDIRECT_FIELD_NAME):
    return basic_switch(request, tenant_id, redirect_field_name)

def switch_region(request, region_name, redirect_field_name=REDIRECT_FIELD_NAME):
    return basic_switch_region(request, region_name, redirect_field_name)





