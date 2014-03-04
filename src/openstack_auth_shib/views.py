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
from .models import PRJ_PRIVATE, PRJ_PUBLIC, PRJ_GUEST
from .forms import BaseRegistForm, FullRegistForm

LOG = logging.getLogger(__name__)

please_msg = _('please, contact the cloud manager')

# TODO
# verify whether it is possible to use just the parent views
# together with the extended backend
# issue: shibboleth redirect converts POST in GET
#        input parameters are lost

def get_shib_attributes(request):
    
    userid = None
    email = None
    fullname = 'Unknown'
    
    if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-shib'):
    
        # the remote user correspond to the ePPN
        userid = request.META['REMOTE_USER']
    
        if 'mail' in request.META:
            email = request.META['mail']
        else:
            raise keystone_exceptions.AuthorizationFailure(_('Cannot retrieve authentication domain'))
        
        if 'cn' in request.META:
            fullname = request.META['cn']
        
        if not userid:
            raise keystone_exceptions.AuthorizationFailure(_('Cannot retrieve authentication domain'))
        
    return (userid, email, fullname)

def get_ostack_attributes(request):
    region = getattr(settings, 'OPENSTACK_KEYSTONE_URL').replace('v2.0','v3')
    domain = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN', 'Default')
    return (domain, region)

@sensitive_post_parameters()
@csrf_protect
@never_cache
def login(request):

    username =''
    try:
    
        username, usermail, fullname = get_shib_attributes(request)
        domain, region = get_ostack_attributes(request)
        
        if username:
        
            map_entry = UserMapping.objects.get(globaluser=username)
            localuser = map_entry.registration.username
            LOG.debug("Mapped user %s on %s" % (username, localuser))

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
            return shortcuts.redirect( '/dashboard-shib/project' )
            
    except (UserMapping.DoesNotExist, keystone_exceptions.NotFound):
        LOG.debug("User %s authenticated but not authorized" % username)
        return register(request)
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
    else:
        return basic_logout(request)


@login_required
def switch(request, tenant_id, redirect_field_name=REDIRECT_FIELD_NAME):
    return basic_switch(request, tenant_id, redirect_field_name)

def switch_region(request, region_name, redirect_field_name=REDIRECT_FIELD_NAME):
    return basic_switch_region(request, region_name, redirect_field_name)


def register(request):

    username, usermail, fullname = get_shib_attributes(request)
    domain, region = get_ostack_attributes(request)
    
    if username:

        if request.method == 'POST':
            reg_form = BaseRegistForm(request.POST)
            if reg_form.is_valid():
            
                return processForm(request, reg_form, domain, region,
                                   username, usermail, fullname)
                
        else:
        
            num_req = RegRequest.objects.filter(externalid=username).count()
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
                     'userid' : username,
                     'form_action_url' : '/dashboard-shib/auth/register/' }
        return shortcuts.render(request, 'registration.html', tempDict)
        
    else:

        if request.method == 'POST':
            reg_form = FullRegistForm(request.POST)
            if reg_form.is_valid():
            
                return processForm(request, reg_form, domain, region)
                
        else:
            reg_form = FullRegistForm()
    
        tempDict = { 'form': reg_form,
                     'form_action_url' : '/dashboard/auth/register/' }
        return shortcuts.render(request, 'registration.html', tempDict)







def processForm(request, reg_form, domain, region, username=None, 
                email=None, fullname='Unknown'):

    try:
        pwd = None
        
        if not username:
            username = reg_form.cleaned_data['username']
            fullname = reg_form.cleaned_data['fullname']
            pwd = reg_form.cleaned_data['pwd']
            email = reg_form.cleaned_data['email']
            ext_account = None
        else:
            ext_account = username
            
        notes = reg_form.cleaned_data['notes']
        
        prj_action = reg_form.cleaned_data['prjaction']
        # empty list for guest prj
        prjlist = list()
        if prj_action == 'selprj':
            for project in reg_form.cleaned_data['selprj']:
                prjlist.append((project, "", PRJ_PUBLIC))
            
        elif prj_action == 'newprj':
            pers_prj = reg_form.cleaned_data['newprj']
            prj_descr = reg_form.cleaned_data['prjdescr']
            prjlist.append((pers_prj, prj_descr, PRJ_PRIVATE))

        LOG.debug("Saving %s" % username)
                
        with transaction.commit_on_success():
    
            queryArgs = {
                'username' : username,
                'fullname' : fullname,
                'domain' : domain,
                'region' : region
            }
            registration = Registration(**queryArgs)
            registration.save()
    
            regArgs = {
                'registration' : registration,
                'password' : pwd,
                'email' : email,
                'notes' : notes
            }
            if ext_account:
                regArgs['externalid'] = ext_account
            regReq = RegRequest(**regArgs)
            regReq.save()

            if len(prjlist) == 0:
                for item in Project.objects.filter(status=PRJ_GUEST):
                    prjlist.append((item.projectname, item.description, item.status))

            for prjitem in prjlist:
        
                try:
                
                    project = Project.objects.get(projectname=prjitem[0])
                
                except Project.DoesNotExist:
                    prjArgs = {
                        'projectname' : prjitem[0],
                        'description' : prjitem[1],
                        'status' : prjitem[2]
                    }
                    project = Project(**prjArgs)
                    project.save()
        
                reqArgs = {
                    'registration' : registration,
                    'project' : project,
                    'notes' : notes
                }
                reqPrj = PrjRequest(**reqArgs)
                reqPrj.save()
            
                
        return shortcuts.redirect('/dashboard')
        
    except:
        LOG.error("Generic failure", exc_info=True)
        tempDict = {
            'error_header' : _("Registration error"),
            'error_text' : "%s, %s" % (_("A failure occurs registering user"), please_msg),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)
                


