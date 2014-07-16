import logging
import re

from django import shortcuts
from django.db import transaction
from django.db import IntegrityError
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.utils.translation import ugettext as _

from django.contrib.auth.decorators import login_required
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from openstack_auth.views import login as basic_login
from openstack_auth.views import logout as basic_logout
from openstack_auth.views import switch as basic_switch
from openstack_auth.views import switch_region as basic_switch_region
from openstack_auth.user import set_session_from_user

try:
    from openstack_auth.views import delete_all_tokens
    from threading import Thread
    old_token_mgm = True
except:
    from openstack_auth.views import delete_token
    old_token_mgm = False

from keystoneclient import exceptions as keystone_exceptions

from horizon import forms

from .models import Registration, Project, RegRequest, PrjRequest, UserMapping
from .models import PRJ_PRIVATE, PRJ_PUBLIC, PRJ_GUEST, PSTATUS_APPR
from .forms import MixRegistForm
from .notifications import notifyManagers, RegistrAvailable

LOG = logging.getLogger(__name__)

def get_ostack_attributes(request):
    region = getattr(settings, 'OPENSTACK_KEYSTONE_URL').replace('v2.0','v3')
    domain = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN', 'Default')
    return (domain, region)

class IdPAttributes():

    SHIB_TYPE = 0
    GOOGLE_TYPE = 1

    def __init__(self, request):
        
        self.ok = False
        
        if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-shib'):
            
            self.ok = True
            self.type = IdPAttributes.SHIB_TYPE
            self.root_url = '/dashboard-shib'
            self.logout_prefix = '/Shibboleth.sso/Logout?return=https://%s:%s' % \
                (request.META['SERVER_NAME'], request.META['SERVER_PORT'])
            
            # the remote user correspond to the ePPN
            self.username = request.META['REMOTE_USER']
    
            if 'mail' in request.META:
                self.email = request.META['mail']
            else:
                self.ok = False
                raise Exception('Cannot retrieve mail address for %s' % self.username)
        
            self.givenname = request.META.get('givenName', 'Unknown')
            self.sn = request.META.get('sn', 'Unknown')

        if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-google'):
        
            self.ok = True
            self.type = IdPAttributes.GOOGLE_TYPE
            self.root_url = '/dashboard-google'
            self.username = request.META['REMOTE_USER']
            self.email = request.GET.get('openid.ext1.value.email', self.username)
            self.givenname = request.GET.get('openid.ext1.value.givenName', 'Unknown')
            self.sn = request.GET.get('openid.ext1.value.sn', 'Unknown')

    def __nonzero__(self):
        return self.ok
    
    def get_logout_url(self, *args):
        
        if self.type == IdPAttributes.SHIB_TYPE:
            result = self.logout_prefix
            if len(args):
                result += args[0]
            else:
                result += '/dashboard'
            return result
        
        if len(args):
            return args[0]
        return '/dashboard'


def build_err_response(request, code, attributes):
    response = shortcuts.redirect(attributes.get_logout_url())
    response.set_cookie('aai_error', code)
    
    if attributes.type == IdPAttributes.GOOGLE_TYPE:
        response.delete_cookie('open_id_session_id', path='/dashboard-google')

    return response

def adj_response(response):
    response.delete_cookie('aai_error')
    return response

def build_safe_redirect(request, location, attributes):
    if attributes:
        response = shortcuts.redirect(attributes.get_logout_url(location))
    
        if attributes.type == IdPAttributes.GOOGLE_TYPE:
            response.delete_cookie('open_id_session_id', path='/dashboard-google')
    else:
        response = shortcuts.redirect(location)
        
    return response

@sensitive_post_parameters()
@csrf_protect
@never_cache
def login(request):

    try:
    
        attributes = IdPAttributes(request)
        domain, region = get_ostack_attributes(request)
        
        if attributes:
        
            map_entry = UserMapping.objects.get(globaluser=attributes.username)
            localuser = map_entry.registration.username
            LOG.debug("Mapped user %s on %s" % (attributes.username, localuser))

            user = authenticate(request=request,
                                username=localuser,
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
            
            return adj_response(shortcuts.redirect( '%s/project' % attributes.root_url))
            
    except (UserMapping.DoesNotExist, keystone_exceptions.NotFound):

        LOG.debug("User %s authenticated but not authorized" % attributes.username)
        return _register(request, attributes)

    except keystone_exceptions.Unauthorized:

        return build_err_response(request, 'NOAUTHZ', attributes)

    except Exception as exc:

        LOG.error(exc.message, exc_info=True)
        return build_err_response(request, 'GENERICERROR', attributes)
        
    return adj_response(basic_login(request))


def logout(request):

    attributes = IdPAttributes(request)
    
    if attributes and attributes.type == IdPAttributes.SHIB_TYPE:
        
        msg = 'Logging out user "%(username)s".' % {'username': request.user.username}
        LOG.info(msg)
        if old_token_mgm:
            if 'token_list' in request.session:
                t = Thread(target=delete_all_tokens,
                    args=(list(request.session['token_list']),))
                t.start()
        else:
            endpoint = request.session.get('region_endpoint')
            token = request.session.get('token')
            if token and endpoint:
                delete_token(endpoint=endpoint, token_id=token.id)

        # update the session cookies (sessionid and csrftoken)
        auth_logout(request)
        return shortcuts.redirect(attributes.get_logout_url())
        
    elif attributes and attributes.type == IdPAttributes.GOOGLE_TYPE:
        
        response = basic_logout(request)
        response.delete_cookie('open_id_session_id', path='/dashboard-google')
        return response
    
    return basic_logout(request)


@login_required
def switch(request, tenant_id, redirect_field_name=REDIRECT_FIELD_NAME):
    return basic_switch(request, tenant_id, redirect_field_name)

def switch_region(request, region_name, redirect_field_name=REDIRECT_FIELD_NAME):
    return basic_switch_region(request, region_name, redirect_field_name)


def _register(request, attributes):

    domain, region = get_ostack_attributes(request)
    
    if request.method == 'POST':
        reg_form = MixRegistForm(request.POST, initial={
            'givenname' : attributes.givenname,
            'sn' : attributes.sn
        })
        if reg_form.is_valid():
            
            return processForm(request, reg_form, domain, attributes)
                
    else:
        
        num_req = RegRequest.objects.filter(externalid=attributes.username).count()
        if num_req:
        
            return build_safe_redirect(request, '/dashboard/auth/dup_login/', attributes)

        reg_form = MixRegistForm(initial={
            'givenname' : attributes.givenname,
            'sn' : attributes.sn
        })
    
    tempDict = { 'form': reg_form,
                 'userid' : attributes.username,
                 'form_action_url' : '%s/auth/register/' % attributes.root_url }
    return adj_response(shortcuts.render(request, 'registration.html', tempDict))


def register(request):

    attributes = IdPAttributes(request)
    
    if attributes:

        return _register(request, attributes)
        
    else:

        domain, region = get_ostack_attributes(request)
        
        if request.method == 'POST':
            reg_form = MixRegistForm(request.POST, initial={'ftype' : 'full'})
            if reg_form.is_valid():
            
                return processForm(request, reg_form, domain)
                
        else:
            reg_form = MixRegistForm(initial={'ftype' : 'full'})
    
        tempDict = { 'form': reg_form,
                     'form_action_url' : '/dashboard/auth/register/' }
        return adj_response(shortcuts.render(request, 'registration.html', tempDict))


def processForm(request, reg_form, domain, attributes=None):

    try:
        pwd = None
        
        if not attributes:
            username = reg_form.cleaned_data['username']
            givenname = reg_form.cleaned_data['givenname']
            sn = reg_form.cleaned_data['sn']
            pwd = reg_form.cleaned_data['pwd']
            email = reg_form.cleaned_data['email']
            ext_account = None
        else:
            username = attributes.username
            #givenname = attributes.givenname
            #sn = attributes.sn
            givenname = reg_form.cleaned_data['givenname']
            sn = reg_form.cleaned_data['sn']
            email = attributes.email
            ext_account = attributes.username
            
        organization = reg_form.cleaned_data['organization']
        phone = reg_form.cleaned_data['phone']
        contactper = reg_form.cleaned_data['contactper']
        notes = reg_form.cleaned_data['notes']
        
        prj_action = reg_form.cleaned_data['prjaction']
        prjlist = list()
        if prj_action == 'selprj':
            for project in reg_form.cleaned_data['selprj']:
                prjlist.append((project, "", PRJ_PUBLIC, False))
            
        elif prj_action == 'newprj':
            prjlist.append((
                reg_form.cleaned_data['newprj'],
                reg_form.cleaned_data['prjdescr'],
                PRJ_PRIVATE if reg_form.cleaned_data['prjpriv'] else PRJ_PUBLIC,
                True
            ))

        LOG.debug("Saving %s" % username)
                
        with transaction.commit_on_success():
    
            queryArgs = {
                'username' : username,
                'givenname' : givenname,
                'sn' : sn,
                'organization' : organization,
                'phone' : phone,
                'domain' : domain
            }
            registration = Registration(**queryArgs)
            registration.save()
    
            regArgs = {
                'registration' : registration,
                'password' : pwd,
                'email' : email,
                'contactper' : contactper,
                'notes' : notes
            }
            if ext_account:
                regArgs['externalid'] = ext_account
            regReq = RegRequest(**regArgs)
            regReq.save()

            #
            # empty list for guest prj
            #
            found_guest = False
            if len(prjlist) == 0:
                for item in Project.objects.filter(status=PRJ_GUEST):
                    found_guest = True
                    prjlist.append((item.projectname, None, 0, False))

            for prjitem in prjlist:
        
                if prjitem[3]:

                    prjArgs = {
                        'projectname' : prjitem[0],
                        'description' : prjitem[1],
                        'status' : prjitem[2]
                    }
                    project = Project.objects.create(**prjArgs)

                else:
                    project = Project.objects.get(projectname=prjitem[0])
        
                reqArgs = {
                    'registration' : registration,
                    'project' : project,
                    'notes' : notes
                }
                
                # workaround for guest tenant (no tenant manager)
                if found_guest:
                    reqArgs['flowstatus'] = PSTATUS_APPR
                
                reqPrj = PrjRequest(**reqArgs)
                reqPrj.save()
            
        
        notifyManagers(RegistrAvailable(username=username))

        return build_safe_redirect(request, '/dashboard/auth/reg_done/', attributes)
    
    except IntegrityError:
    
        return build_safe_redirect(request, '/dashboard/auth/name_exists/', attributes)

    except:
    
        LOG.error("Generic failure", exc_info=True)
        return build_safe_redirect(request, '/dashboard/auth/reg_failure/', attributes)
                

def reg_done(request):
    tempDict = {
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_registration_ok.html', tempDict)

def reg_failure(request):
    tempDict = {
        'error_header' : _("Registration error"),
        'error_text' : _("A failure occurs registering user"),
        'contacts' : getattr(settings, 'MANAGERS', None),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)

def name_exists(request):
    tempDict = {
        'error_header' : _("Registration error"),
        'error_text' : _("Login name or project already exists, please, choose another one"),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)

def dup_login(request):
    tempDict = {
        'error_header' : _("Registration error"),
        'error_text' : _("Request has already been sent"),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)




