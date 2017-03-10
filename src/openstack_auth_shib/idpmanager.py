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
import urllib
import glob
import json
import os.path

from django.conf import settings

from .models import OS_LNAME_LEN


LOG = logging.getLogger(__name__)

#
# Provider configuration table
#
# { 
#   'context' : '/dashboard-openidc', 
#   'path' : '/dashboard-openidc/auth/login', 
#   'description' : 'INDIGO AAI', 
#   'logo' : '/dashboard/static/dashboard/img/logoINDIGO.png',
#   'uid_tag' : 'OIDC-preferred_username',
#   'org_tag' : 'OIDC-organisation_name' 
# }
#

def get_manager(request):

    if not 'REMOTE_USER' in request.META:
        return None

    if request.META.get('AUTH_TYPE','') == 'shibboleth':
        return SAML2_IdP(request)
    
    for item in settings.HORIZON_CONFIG['identity_providers']:
        if request.path.startswith(item['context']):
            return OIDC_IdP(request, item)

    return None



class SAML2_IdP:

    def __init__(self, request):
    
        self.root_url = '/' + request.path.split('/')[1]
        self.logout_prefix = '/Shibboleth.sso/Logout?return=https://%s:%s' % \
            (request.META['SERVER_NAME'], request.META['SERVER_PORT'])
            
        # the remote user corresponds to the ePPN
        self.username = request.META['REMOTE_USER']
        if len(self.username) > OS_LNAME_LEN:
            self.username = self.username[0:OS_LNAME_LEN]
        
        tmpmail = request.META.get('mail', None)
        if tmpmail:
            self.email = tmpmail.split(';')[0]
        else:
            self.email = None
        self.givenname = request.META.get('givenName', None)
        self.sn = request.META.get('sn', None)
        
        # organization as in urn:mace:dir:attribute-def:eduPersonPrincipalName
        idx = request.META['REMOTE_USER'].find('@')
        if idx > 0:
            self.provider = request.META['REMOTE_USER'][idx+1:]
        else:
            self.provider = None
        
    def get_logout_url(self, *args):
        
        result = self.logout_prefix
        if len(args):
            result += args[0]
        else:
            result += '/dashboard'
        return result        
    
    def postproc_logout(self, response):
        return response


class OIDC_IdP:

    def __init__(self, request, params):
    
        self.root_url = params['context']
        self.logout_prefix = '%s/redirect-uri?logout=https://%s:%s/dashboard' % \
            (params['context'], request.META['SERVER_NAME'], request.META['SERVER_PORT'])

        self.username = request.META.get(params.get('uid_tag', 'REMOTE_USER'))
        if len(self.username) > OS_LNAME_LEN:
            self.username = self.username[0:OS_LNAME_LEN]

        self.givenname = request.META.get(params.get('g_name_tag', 'OIDC-given_name'), None)
        self.sn = request.META.get(params.get('s_name_tag', 'OIDC-family_name'), None)
        self.email = request.META.get(params.get('email_tag', 'OIDC-email'), None)
        self.provider = request.META.get(params.get('org_tag', 'OIDC-organisation_name'), 'OIDC')

    def get_logout_url(self, *args):
        return self.logout_prefix
    
    def postproc_logout(self, response):
        return response



def get_idp_list(excl_list=list()):
    raise Exception("Unsupported")






