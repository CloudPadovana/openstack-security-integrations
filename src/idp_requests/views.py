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

from django import shortcuts
from django.conf import settings
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
#from django.core.urlresolvers import reverse_lazy

from horizon import exceptions
from horizon import forms

from openstack_auth_shib.views import IdPAttributes
from openstack_auth_shib.models import Registration, UserMapping

LOG = logging.getLogger(__name__)

#class ManageView(forms.ModalFormView):
#    form_class = IdpManageForm
#    template_name = 'project/idp_requests/idp_request.html'
#    success_url = reverse_lazy('horizon:project:overview:index')

def manage(request):

    myproviders = set()
    
    allmaps = UserMapping.objects.filter(registration__userid=request.user.id)
    for umap in allmaps:
        idx = umap.globaluser.find('@')
        if idx > 0:
            myproviders.add(umap.globaluser[idx+1:])

    ctx = dict()

    attributes = IdPAttributes(request)
    if attributes:
        ctx['currpath'] = '%s/project/idp_requests/suspend/' % attributes.root_url
    else:
        ctx['currpath'] = '/dashboard/project/idp_requests/suspend/'
    
    if not 'infn.it' in myproviders:
        
        if settings.HORIZON_CONFIG.get('infntesting_enabled', False):
            ctx['infntestquery'] = urllib.urlencode({
                'url' : '/Shibboleth.sso/Login?entityID=%s&target=%s' % \
                    ('https%3A%2F%2Fidp.infn.it%2Ftesting%2Fsaml2%2Fidp%2Fmetadata.php',
                    '%2Fdashboard-shib%2Fproject%2Fidp_requests%2Fresume%2F')
            })
        else:
            ctx['infnprodquery'] = urllib.urlencode({
                'url' : '/Shibboleth.sso/Login?entityID=%s&target=%s' % \
                    ('https%3A%2F%2Fidp.infn.it%2Fsaml2%2Fidp%2Fmetadata.php',
                    '%2Fdashboard-shib%2Fproject%2Fidp_requests%2Fresume%2F')
            })
    
    if settings.HORIZON_CONFIG.get('idem_enabled', False):
    
        ctx['idemquery'] = urllib.urlencode({
            'url' : '/dashboard-shib/project/idp_requests/resume/'
        })
    
    if not ('gmail.com' in myproviders or 'google.com' in myproviders) \
        and settings.HORIZON_CONFIG.get('google_enabled', False):
        
        ctx['googlequery'] = urllib.urlencode({
            'url' : '/dashboard-google/project/idp_requests/resume/'
        })
    
    ctx['showidptable'] = len(ctx) > 1
    
    return shortcuts.render(request, 
                            'project/idp_requests/idp_request.html',
                            ctx)
    
    

def suspend(request):
    
    new_url = request.GET['url']
    attributes = IdPAttributes(request)

    response = None
    
    if attributes:
        LOG.debug("Calling suspend with %s" % attributes.get_logout_url(new_url))
        response = shortcuts.redirect(attributes.get_logout_url(new_url))
    
        if attributes.type == IdPAttributes.GOOGLE_TYPE:
            response.delete_cookie('open_id_session_id', path='/dashboard-google')
    
    else:
        response = shortcuts.redirect(new_url)

    response.set_cookie('pivot', request.user.id)
    return response



def resume(request):

    userid = request.COOKIES['pivot']

    attributes = IdPAttributes(request)
    
    response = None
    
    if attributes:
    
        with transaction.commit_on_success():
        
            extId = attributes.username
        
            registr = Registration.objects.filter(userid=userid)[0]
            #
            # TODO check EXT_ACCT_LEN
            #
            u_map = UserMapping(
                globaluser=extId,
                registration=registr
            )
            u_map.save()

        LOG.debug('Calling resume with %s/project' % attributes.root_url)
        response = shortcuts.redirect(attributes.root_url + '/project')

    else:
        response = shortcuts.redirect('/dashboard')

    response.delete_cookie('pivot')
    return response




