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

from django import shortcuts
from django.db import IntegrityError
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from horizon import exceptions
from horizon import forms

from openstack_auth_shib.idpmanager import get_manager, get_idp_list
from openstack_auth_shib.models import Registration, UserMapping

LOG = logging.getLogger(__name__)

def manage(request):

    myproviders = set()
    
    allmaps = UserMapping.objects.filter(registration__userid=request.user.id)
    for umap in allmaps:
        idx = umap.globaluser.find('@')
        if idx > 0:
            myproviders.add(umap.globaluser[idx+1:])

    ctx = dict()

    attributes = get_manager(request)
    if attributes:
        ctx['currpath'] = '%s/idmanager/idp_requests/suspend/' % attributes.root_url
    else:
        ctx['currpath'] = '/dashboard/idmanager/idp_requests/suspend/'
    
    ctx['idp_data_list'] = get_idp_list(myproviders)
    ctx['providers'] = myproviders
    
    return shortcuts.render(request, 'idmanager/idp_requests/idp_request.html', ctx)
    
    

def suspend(request):
    
    new_url = request.GET['url']
    attributes = get_manager(request)

    response = None
    
    if attributes:
        LOG.debug("Calling suspend with %s" % attributes.get_logout_url(new_url))
        response = shortcuts.redirect(attributes.get_logout_url(new_url))
        response = attributes.postproc_logout(response)
    
    else:
        response = shortcuts.redirect(new_url)

    response.set_cookie('pivot', request.user.id)
    return response



def resume(request):

    userid = request.COOKIES['pivot']

    attributes = get_manager(request)
    
    response = None
    
    if attributes:
    
        try:
            with transaction.atomic():
        
                extId = attributes.username
        
                registr = Registration.objects.filter(userid=userid)[0]
                u_map = UserMapping(globaluser=extId, registration=registr)
                u_map.save(force_insert=True)

            LOG.debug('Calling resume with %s/idmanager' % attributes.root_url)
            response = shortcuts.redirect(attributes.root_url + '/idmanager')
        
        except IntegrityError:
            LOG.error("Duplicate map for %s in %s" % (userid, extId))
            response = shortcuts.redirect(reverse('logout'))
            response.set_cookie('aai_error', 'NOREMAP')
        except:
            LOG.error("Cannot map userid %s" % userid, exc_info=True)
            response = shortcuts.redirect(reverse('logout'))
            response.set_cookie('aai_error', 'GENERICERROR')

    else:
        response = shortcuts.redirect('/dashboard')

    response.delete_cookie('pivot')
    return response




