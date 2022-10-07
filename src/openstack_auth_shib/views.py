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
from urllib.parse import urlencode

from django import shortcuts
from django import http as django_http
from django.conf import settings
from django.contrib import auth as django_auth
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.translation import gettext as _

from django.contrib.auth.decorators import login_required
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.csrf import csrf_exempt

from openstack_auth import user as auth_user
from openstack_auth.views import login as basic_login
from openstack_auth.views import websso as basic_websso
from openstack_auth.views import logout as basic_logout
from openstack_auth.views import switch as basic_switch
from openstack_auth.views import switch_region as basic_switch_region
from openstack_auth.utils import get_websso_url
from openstack_auth.utils import clean_up_auth_url
from openstack_auth.exceptions import KeystoneAuthException

from openstack_dashboard.api import keystone as keystone_api

from horizon import forms

from .models import UserMapping
from .models import RegRequest
from .models import PrjRequest
from .models import Project
from .models import Expiration
from .models import PRJ_COURSE
from .forms import RegistrForm
from .idpmanager import Federated_Account
from .idpmanager import checkFederationSetup
from .utils import parse_course_info

LOG = logging.getLogger(__name__)
AUTHZCOOKIE = "keystoneidpid"

@sensitive_post_parameters()
@csrf_protect
@never_cache
def login(request):

    if request.method == 'POST':
        auth_type = request.POST.get('auth_type', 'credentials')
        auth_url = request.POST.get('region', None)

        if  auth_type != 'credentials' and auth_url != None:
            url = get_websso_url(request, auth_url, auth_type)
            tmpresp = shortcuts.redirect(url)
            tmpresp.set_cookie(AUTHZCOOKIE, auth_type)
            return tmpresp

    result = basic_login(request)
    if request.user.is_authenticated and request.user.is_superuser:
        checkFederationSetup(request)
    return result

@sensitive_post_parameters()
@csrf_exempt
@never_cache
def websso(request):

    # imported from base class
    if settings.WEBSSO_USE_HTTP_REFERER:
        referer = request.META.get('HTTP_REFERER',
                                   settings.OPENSTACK_KEYSTONE_URL)
        auth_url = clean_up_auth_url(referer)
    else:
        auth_url = settings.OPENSTACK_KEYSTONE_URL
    token = request.POST.get('token')

    try:
        request.user = django_auth.authenticate(request,
                                                auth_url = auth_url,
                                                token = token)
    except KeystoneAuthException as exc:
        return auth_error(request)

    auth_user.set_session_from_user(request, request.user)
    django_auth.login(request, request.user)
    if request.session.test_cookie_worked():
        request.session.delete_test_cookie()
    sso_resp = django_http.HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
    sso_resp.delete_cookie(AUTHZCOOKIE)
    return sso_resp

def logout(request):

    use_slo = settings.HORIZON_CONFIG.get('enable_slo', False)
    #use_slo = use_slo and request.user.is_federated
    use_slo = use_slo and not 'finalstep' in request.GET

    if not use_slo:
        return basic_logout(request)

    try:
        site_name = request.META['SERVER_NAME']
        site_port = int(request.META['SERVER_PORT'])

        redir_url = 'https://%s:%d/dashboard/auth/logout?finalstep=true'

        utoken = request.session.get('unscoped_token')
        token_data = keystone_api.keystoneclient(request).tokens.get_token_data(utoken)

        redir_str = None
        if "openid" in token_data['token']['methods']:
            redir_para = 'logout'
            redir_str = "https://%s:%d/v3/auth/OS-FEDERATION/websso/openid/redirect?%s"
        elif "mapped" in token_data['token']['methods']:
            redir_para = 'return'
            redir_str = 'https://%s:%d/Shibboleth.sso/Logout?%s' 

        if redir_str:
            param_str = urlencode({ redir_para : redir_url  % (site_name, site_port)})
            srv_table = settings.HORIZON_CONFIG.get('srv_bind_table', {})
            ks_name = srv_table.get(site_name, site_name)
            jumpto = redir_str % (ks_name, site_port, param_str)
            
            return django_http.HttpResponseRedirect(jumpto)

    except:
        LOG.error("SLO failure", exc_info=True)

    return basic_logout(request)

@login_required
def switch(request, tenant_id, redirect_field_name=REDIRECT_FIELD_NAME):
    # workaround for switch redirect: don't use the redirect field name
    return basic_switch(request, tenant_id, '')

@login_required
def switch_region(request, region_name, redirect_field_name=REDIRECT_FIELD_NAME):
    # workaround for switch redirect: don't use the redirect field name
    return basic_switch_region(request, region_name, '')

class RegistrView(forms.ModalFormView):
    form_class = RegistrForm
    template_name = 'registration.html'

    def get_initial(self):
        result = super(RegistrView, self).get_initial()
        if not hasattr(self, "attributes"):
            self.attributes = Federated_Account(self.request)

        if self.attributes:
            result['needpwd'] = False
            result['username'] = self.attributes.username
            result['federated'] = "true"
            if self.attributes.givenname:
                result['givenname'] = self.attributes.givenname
            if self.attributes.sn:
                result['sn'] = self.attributes.sn
            if self.attributes.email:
                result['email'] = self.attributes.email
            if self.attributes.provider:
                result['organization'] = self.attributes.provider
        else:
            result['needpwd'] = True
            result['federated'] = "false"

        prjname_param = self.request.GET.get('projectname', None)
        if prjname_param:
            result['prjaction'] = 'selprj'
            result['selprj'] = prjname_param

        org = self.request.GET.get('org', None)
        if org:
            result['organization'] = org

        org_unit = self.request.GET.get('ou', None)
        if org_unit:
            result['org_unit'] = org_unit

        result['custom_org'] = ""
        result['contactper'] = "unknown"

        return result

    def get_context_data(self, **kwargs):
        context = super(RegistrView, self).get_context_data(**kwargs)
        if not hasattr(self, "attributes"):
            self.attributes = Federated_Account(self.request)

        if self.attributes:
            context['userid'] = self.attributes.username
            context['form_action_url'] = '%s/auth/register/' % self.attributes.root_url
        else:
            context['form_action_url'] = '/dashboard/auth/register/'
        return context

    def get(self, request, *args, **kwargs):

        if not hasattr(self, "attributes"):
            self.attributes = Federated_Account(self.request)

        if self.attributes:

            if UserMapping.objects.filter(globaluser=self.attributes.username).count() \
                and not 'projectname' in request.GET:
                return alreay_registered(self.request)

            if RegRequest.objects.filter(externalid=self.attributes.username).count():
                return dup_login(self.request)

        return super(RegistrView, self).get(request, args, kwargs)

def reg_done(request):
    tempDict = {
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_registration_ok.html', tempDict)

def alreay_registered(request):
    tempDict = {
        'error_header' : _("Registration error"),
        'error_text' : _("Your account has already been registered"),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)

def alreay_subscribed(request):
    tempDict = {
        'error_header' : _("Registration error"),
        'error_text' : _("Your are already member of the project"),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)

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
        'error_text' : _("Request has already been sent but it is not yet authorized"),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)

#
# Used in /etc/shibboleth/shibboleth2.xml
#
def auth_error(request):

    try:
        if AUTHZCOOKIE in request.COOKIES:
            idp_tag = request.COOKIES[AUTHZCOOKIE]

            idpdata = settings.HORIZON_CONFIG['identity_providers'][idp_tag]
            dest_url = idpdata['path'].replace('register', 'authzchk')
            tmpresp = django_http.HttpResponseRedirect("%s?idp_tag=%s" % (dest_url, idp_tag))
            tmpresp.delete_cookie(AUTHZCOOKIE)

            return tmpresp
    except:
        LOG.error("Cookie detection error", exc_info=True)

    if 'errorText' in request.GET:
        LOG.error("Bad message from keystone: %s", request.GET['errorText'])
        err_msg = _("An error occurs contacting the identity service")
    else:
        err_msg = _("User not registered or authorization failed")
    
    tempDict = {
        'error_header' : _("Access denied"),
        'error_text' : err_msg,
        'contacts' : getattr(settings, 'MANAGERS', None),
        'redirect_url' : '/dashboard',
        'redirect_label' : _("Home")
    }
    return shortcuts.render(request, 'aai_error.html', tempDict)

#
# Splash page for courses
#
def course(request, project_name):

    course_table = settings.HORIZON_CONFIG.get('course_for', {})
    if len(course_table) == 0:
        tempDict = {
            'error_header' : _("Course management is not supported"),
            'error_text' : _("Course management is not supported"),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)

    project = Project.objects.filter(projectname=project_name)

    if len(project) == 0:
        tempDict = {
            'error_header' : _("Course not found"),
            'error_text' : "%s: %s" % (_("Course not found"), project_name),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)

    if project[0].status != PRJ_COURSE:
        tempDict = {
            'error_header' : _("Course not yet available"),
            'error_text' : "%s: %s" % (_("Course not yet available"), project_name),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)

    info_table = parse_course_info(project[0].description)

    idpref = course_table.get(info_table['org'], None)
    if not idpref:
        tempDict = {
            'error_header' : _("Course management error"),
            'error_text' : "%s: %s" % (_("Course management error"), project_name),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        }
        return shortcuts.render(request, 'aai_error.html', tempDict)

    reg_path = settings.HORIZON_CONFIG['identity_providers'][idpref]['path']

    info_table['project'] = project_name
    info_table['registration_url'] = reg_path

    return shortcuts.render(request, 'course.html', info_table)

def authzchk(request):
    attributes = Federated_Account(request)

    tmpresp = None
    idp_tag = request.GET.get('idp_tag', None)
    try:
        if attributes:
            umap = UserMapping.objects.filter(globaluser = attributes.username)
            if idp_tag and len(umap) == 0:
                idpdata = settings.HORIZON_CONFIG['identity_providers'][idp_tag]
                tmpresp = django_http.HttpResponseRedirect(idpdata['path'])
            elif len(umap) > 0:
                e_msg = None
                q_args = { 'registration' : umap[0].registration }
                pend_req = PrjRequest.objects.filter(**q_args)
                if len(pend_req):
                    e_msg = _("User is waiting for affiliation to %s")
                    e_msg = e_msg % pend_req[0].project.projectname
                elif Expiration.objects.filter(**q_args).count() == 0:
                    e_msg = _("No affiliation available for the user")

                if e_msg:
                    tmpresp = shortcuts.render(request, 'aai_error.html', {
                        'error_header' : _("Access denied"),
                        'error_text' : e_msg,
                        'redirect_url' : '/dashboard',
                        'redirect_label' : _("Home")
                    })

    except:
        LOG.error("Cookie detection error", exc_info=True)

    if not tmpresp:
        tmpresp = shortcuts.render(request, 'aai_error.html', {
            'error_header' : _("Access denied"),
            'error_text' : _("User not registered or authorization failed"),
            'redirect_url' : '/dashboard',
            'redirect_label' : _("Home")
        })

    return tmpresp

def resetsso(request):

    hname = request.META['SERVER_NAME']
    hport = int(request.META['SERVER_PORT'])
    redir_url = 'https://%s:%d/dashboard/auth/login' % (hname, hport)

    try:
        method = None
        for idpid, idpdata in list(settings.HORIZON_CONFIG['identity_providers'].items()):
            if idpdata['context'] in request.META['REQUEST_URI']:
                method = settings.WEBSSO_IDP_MAPPING[idpid][1]
                break

        if method == "mapped":
            param_str = urlencode({ 'return' : redir_url })
            redir_str = 'https://%s:%d/Shibboleth.sso/Logout?%s' % (hname, hport, param_str)
        elif method in [ "openid", "oidc", "openidc"]:
            param_str = urlencode({ 'logout' : redir_url })
            redir_str = ("https://%s:%d" + settings.OIDC_REDIRECT_PATH + "?%s") % (hname, hport, param_str)
        else:
            redir_str = redir_url
    except:
        LOG.error("SSO reset error", exc_info=True)

    return django_http.HttpResponseRedirect(redir_str)

