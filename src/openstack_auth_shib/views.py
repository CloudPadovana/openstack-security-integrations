#  Copyright (c) 2014 INFN - "Istituto Nazionale di Fisica Nucleare" - Italy
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License. 

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
from openstack_auth import exceptions as auth_exceptions

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
from .notifications import notifyManagers, notification_render, REGISTR_AVAIL_TYPE
from .idpmanager import get_manager
from .utils import get_user_home

LOG = logging.getLogger(__name__)

def get_ostack_attributes(request):
    region = getattr(settings, 'OPENSTACK_KEYSTONE_URL').replace('v2.0','v3')
    domain = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN', 'Default')
    return (domain, region)

def build_err_response(request, err_msg, attributes):
    response = shortcuts.redirect(attributes.get_logout_url())
    if attributes:
        response = attributes.postproc_logout(response)

    response.set_cookie('logout_reason', err_msg)

    return response

def build_safe_redirect(request, location, attributes):
    if attributes:
        response = shortcuts.redirect(attributes.get_logout_url(location))
        response = attributes.postproc_logout(response)
    else:
        response = shortcuts.redirect(location)
        
    return response

@sensitive_post_parameters()
@csrf_protect
@never_cache
def login(request):

    try:
    
        attributes = get_manager(request)
        domain, auth_url = get_ostack_attributes(request)
        
        if attributes:
        
            map_entry = UserMapping.objects.get(globaluser=attributes.username)
            localuser = map_entry.registration.username
            LOG.debug("Mapped user %s on %s" % (attributes.username, localuser))

            kwargs = {
                'auth_url' : auth_url,
                'request' : request,
                'username' : localuser,
                'password' : None,
                'user_domain_name' : domain
            }
            user = authenticate(**kwargs)

            auth_login(request, user)
            if request.user.is_authenticated():
                set_session_from_user(request, request.user)
                
                default_region = (settings.OPENSTACK_KEYSTONE_URL, "Default Region")
                regions = dict(getattr(settings, 'AVAILABLE_REGIONS', [default_region]))
                
                region = request.user.endpoint
                region_name = regions.get(region)
                request.session['region_endpoint'] = region
                request.session['region_name'] = region_name
                request.session['global_user'] = attributes.username
            
            return shortcuts.redirect(get_user_home(user))
            
    except (UserMapping.DoesNotExist, keystone_exceptions.NotFound):

        LOG.debug("User %s authenticated but not authorized" % attributes.username)
        return _register(request, attributes)

    except (keystone_exceptions.Unauthorized, auth_exceptions.KeystoneAuthException):

        return build_err_response(request, _("User not authorized: invalid or disabled"), attributes)

    except Exception as exc:

        LOG.error(exc.message, exc_info=True)
        err_msg = "A failure occurs authenticating user\nPlease, contact the cloud managers"
        return build_err_response(request, _(err_msg), attributes)
        
    return basic_login(request)


def logout(request):

    attributes = get_manager(request)
    
    if attributes:
        
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
        
        response = shortcuts.redirect(attributes.get_logout_url())
        return attributes.postproc_logout(response)
        
    return basic_logout(request)


@login_required
def switch(request, tenant_id, redirect_field_name=REDIRECT_FIELD_NAME):
    # workaround for switch redirect: don't use the redirect field name
    return basic_switch(request, tenant_id, '')

def switch_region(request, region_name, redirect_field_name=REDIRECT_FIELD_NAME):
    # workaround for switch redirect: don't use the redirect field name
    return basic_switch_region(request, region_name, '')


def _register(request, attributes):

    domain, region = get_ostack_attributes(request)
    
    init_dict = dict()
    if attributes.givenname:
        init_dict['givenname'] = attributes.givenname
    if attributes.sn:
        init_dict['sn'] = attributes.sn
    if attributes.email:
        init_dict['email'] = attributes.email
    if attributes.provider:
        init_dict['organization'] = attributes.provider
    
    if request.method == 'POST':
        reg_form = MixRegistForm(request.POST, initial=init_dict)
        if reg_form.is_valid():
            
            return processForm(request, reg_form, domain, attributes)
                
    else:
        
        num_req = RegRequest.objects.filter(externalid=attributes.username).count()
        if num_req:
        
            return build_safe_redirect(request, '/dashboard/auth/dup_login/', attributes)

        reg_form = MixRegistForm(initial=init_dict)
    
    tempDict = { 'form': reg_form,
                 'userid' : attributes.username,
                 'form_action_url' : '%s/auth/register/' % attributes.root_url }
    return shortcuts.render(request, 'registration.html', tempDict)


def register(request):

    attributes = get_manager(request)
    
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
            givenname = reg_form.cleaned_data['givenname']
            sn = reg_form.cleaned_data['sn']
            email = reg_form.cleaned_data['email']
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
                
        with transaction.atomic():
    
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
            
            LOG.debug("Saved %s" % username)

            #
            # empty list for guest prj
            #
            if len(prjlist) == 0:
                for item in Project.objects.filter(status=PRJ_GUEST):
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
                
                reqPrj = PrjRequest(**reqArgs)
                reqPrj.save()
            
        noti_sbj, noti_body = notification_render(REGISTR_AVAIL_TYPE, {'username' : username})
        notifyManagers(noti_sbj, noti_body)

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

#
# Used in /etc/shibboleth/shibboleth2.xml
#
def auth_error(request):

    if 'errorText' in request.GET:
        err_msg = "%s: [%s]" % (_("Original error"), request.GET['errorText'])
    else:
        err_msg = _("A failure occurs authenticating user")
    
    tempDict = {
        'error_header' : _("Authentication error"),
        'error_text' : err_msg,
        'contacts' : getattr(settings, 'MANAGERS', None),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)



