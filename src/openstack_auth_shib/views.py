import logging
import re

from threading import Thread

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
from openstack_auth.views import delete_all_tokens
from openstack_auth.user import set_session_from_user

from keystoneclient import exceptions as keystone_exceptions

from horizon import forms

from .models import Registration, Project, RegRequest, PrjRequest, UserMapping
from .models import PRJ_PRIVATE, PRJ_PUBLIC, PRJ_GUEST, PSTATUS_APPR
from .forms import BaseRegistForm, FullRegistForm
from .notifications import notifyManagers, RegistrAvailable

LOG = logging.getLogger(__name__)

please_msg = _('please, contact the cloud manager')

def get_ostack_attributes(request):
    region = getattr(settings, 'OPENSTACK_KEYSTONE_URL').replace('v2.0','v3')
    domain = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN', 'Default')
    return (domain, region)

class IdPAttributes():

    def __init__(self, request):
        
        self.ok = False
        
        if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-shib'):
            
            self.ok = True
            self.root_url = '/dashboard-shib'
            
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
            self.root_url = '/dashboard-google'
            self.username = request.META['REMOTE_USER']
            self.email = request.GET.get('openid.ext1.value.email', self.username)
            self.givenname = request.GET.get('openid.ext1.value.givenName', 'Unknown')
            self.sn = request.GET.get('openid.ext1.value.sn', 'Unknown')

    def __nonzero__(self):
        return self.ok


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
            return shortcuts.redirect( '%s/project' % attributes.root_url)
            
    except (UserMapping.DoesNotExist, keystone_exceptions.NotFound):
        LOG.debug("User %s authenticated but not authorized" % attributes.username)
        return _register(request, attributes)
    except Exception as exc:
        LOG.error(exc.message, exc_info=True)
        tempDict = {
            'error_header' : _("Authentication error"),
            'error_text' : "%s, %s" % (_("A failure occurs authenticating user"), please_msg),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)
        
    return basic_login(request)


def logout(request):

    if request.path.startswith('/dashboard-shib'):
    
        msg = 'Logging out user "%(username)s".' % {'username': request.user.username}
        LOG.info(msg)
        if 'token_list' in request.session:
            t = Thread(target=delete_all_tokens,
                   args=(list(request.session['token_list']),))
            t.start()
        
        # update the session cookies (sessionid and csrftoken)
        auth_logout(request)
        ret_URL = "https://%s:%s/dashboard" % (request.META['SERVER_NAME'],
                                               request.META['SERVER_PORT'])
        return shortcuts.redirect('/Shibboleth.sso/Logout?return=%s' % ret_URL)
        
    elif request.path.startswith('/dashboard-google'):
        
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
        reg_form = BaseRegistForm(request.POST)
        if reg_form.is_valid():
            
            return processForm(request, reg_form, domain, attributes)
                
    else:
        
        num_req = RegRequest.objects.filter(externalid=attributes.username).count()
        if num_req:
            tempDict = {
                'error_header' : _("Registration error"),
                'error_text' : _("Request has already been sent"),
                'redirect_url' : '/dashboard',
                'redirect_label' : _("Home")
            }
            return shortcuts.render(request, 'aai_error.html', tempDict)

        reg_form = BaseRegistForm()
    
    tempDict = { 'form': reg_form,
                 'userid' : attributes.username,
                 'form_action_url' : '%s/auth/register/' % attributes.root_url }
    return shortcuts.render(request, 'registration.html', tempDict)


def register(request):

    attributes = IdPAttributes(request)
    
    if attributes:

        return _register(request, attributes)
        
    else:

        domain, region = get_ostack_attributes(request)
        
        if request.method == 'POST':
            reg_form = FullRegistForm(request.POST)
            if reg_form.is_valid():
            
                return processForm(request, reg_form, domain)
                
        else:
            reg_form = FullRegistForm()
    
        tempDict = { 'form': reg_form,
                     'form_action_url' : '/dashboard/auth/register/' }
        return shortcuts.render(request, 'registration.html', tempDict)


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
            givenname = attributes.givenname
            sn = attributes.sn
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

        if ext_account:
            redir_url = '/Shibboleth.sso/Logout?return=https://%s:%s/dashboard' % \
                (request.META['SERVER_NAME'], request.META['SERVER_PORT'])
        else:
            redir_url = '/dashboard'

        tempDict = {
            'error_header' : _("Registration done"),
            'error_text' : _("Your registration has been submitted"),
            'redirect_url' : redir_url,
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)
    
    except IntegrityError:
        tempDict = {
            'error_header' : _("Registration error"),
            'error_text' : _("Login name or project already exists, please, choose another one"),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)

    except:
        LOG.error("Generic failure", exc_info=True)
        tempDict = {
            'error_header' : _("Registration error"),
            'error_text' : "%s, %s" % (_("A failure occurs registering user"), please_msg),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)
                


