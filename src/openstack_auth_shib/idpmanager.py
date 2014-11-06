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

from django.conf import settings

from .models import OS_LNAME_LEN


LOG = logging.getLogger(__name__)

def get_manager(request):

    #
    # TODO remove dashboard-shib, check shib session in META
    #
    if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-shib'):
        return SAML2_IdP(request)
    
    if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-google'):
        return Google_IdP(request)
        
    return None



class SAML2_IdP:

    def __init__(self, request):
    
        self.root_url = '/dashboard-shib'
        self.logout_prefix = '/Shibboleth.sso/Logout?return=https://%s:%s' % \
            (request.META['SERVER_NAME'], request.META['SERVER_PORT'])
            
        # the remote user corresponds to the ePPN
        self.username = request.META['REMOTE_USER']
        if len(self.username) > OS_LNAME_LEN:
            self.username = self.username[0:OS_LNAME_LEN]
    
        if 'mail' in request.META:
            self.email = request.META['mail']
        else:
            raise Exception('Cannot retrieve mail address for %s' % self.username)
        
        self.givenname = request.META.get('givenName', 'Unknown')
        self.sn = request.META.get('sn', 'Unknown')
        
    def get_logout_url(self, *args):
        
        result = self.logout_prefix
        if len(args):
            result += args[0]
        else:
            result += '/dashboard'
        return result        
    
    def postproc_logout(self, response):
        return response



class Google_IdP:

    def __init__(self, request):
    
        self.root_url = '/dashboard-google'
        self.logout_prefix = ''
        self.username = request.META['REMOTE_USER']
        if len(self.username) > OS_LNAME_LEN:
            self.username = self.username[0:OS_LNAME_LEN]
        self.email = request.GET.get('openid.ext1.value.email', self.username)
        self.givenname = request.GET.get('openid.ext1.value.givenName', 'Unknown')
        self.sn = request.GET.get('openid.ext1.value.sn', 'Unknown')

    def get_logout_url(self, *args):
        
        if len(args):
            return args[0]
        return '/dashboard'
    
    def postproc_logout(self, response):
        response.delete_cookie('open_id_session_id', path='/dashboard-google')
        return response




def get_idp_list(excl_list=list()):

    result = list()
    
    idp_list = settings.HORIZON_CONFIG.get('identity_providers', [])

    for idp_data in idp_list:
        #
        # TODO check if item is well-formed, see _login.html
        # Accepted keys:
        # id: IdP id (infn.it, unipd.it, etc)
        # path: URL path prefix (/dashboard-shib, /dashboard-google, etc.)
        # description: IdP short description
        # logo: URL path for the logo (/static/dashboard/img/logoInfnAAI.png)
        #
        if not idp_data['id'] in excl_list:
            resume_url = '%s/project/idp_requests/resume/' % idp_data['path']
            idp_data['resume_query'] = urllib.urlencode({'url' : resume_url})
            result.append()

'''    
    if not 'infn.it' in excl_list and settings.HORIZON_CONFIG.get('infntesting_enabled', False):
        result.append(IdPData('infntest', 'INFN AAI', 'logoInfnAAI.png', 
            urllib.urlencode({ 'url' : '/Shibboleth.sso/Login?entityID=%s&target=%s' % \
                ('https%3A%2F%2Fidp.infn.it%2Ftesting%2Fsaml2%2Fidp%2Fmetadata.php',
                '%2Fdashboard-shib%2Fproject%2Fidp_requests%2Fresume%2F')
            })))
    
    if not 'infn.it' in excl_list and not settings.HORIZON_CONFIG.get('infntesting_enabled', False):
        result.append(IdPData('infn', 'INFN AAI', 'logoInfnAAI.png', 
            urllib.urlencode({ 'url' : '/Shibboleth.sso/Login?entityID=%s&target=%s' % \
                ('https%3A%2F%2Fidp.infn.it%2Fsaml2%2Fidp%2Fmetadata.php',
                '%2Fdashboard-shib%2Fproject%2Fidp_requests%2Fresume%2F')
            })))
    
    if settings.HORIZON_CONFIG.get('idem_enabled', False):
        result.append(IdPData('idem', 'IDEM Federation', 'logoIDEM.png',
            urllib.urlencode({ 'url' : '/dashboard-shib/project/idp_requests/resume/' })))
    
    if not ('gmail.com' in excl_list or 'google.com' in excl_list) \
        and settings.HORIZON_CONFIG.get('google_enabled', False):
        
        result.append(IdPData('google', 'Google Provider', 'logoGoogle.png',
            urllib.urlencode({ 'url' : '/dashboard-google/project/idp_requests/resume/' })))
'''    
    return result


class IdPData:

    def __init__(self, name, descr, logo, resume_query):
        self.name = name
        self.descr = descr
        self.logo = logo
        self.resume_query = resume_query









