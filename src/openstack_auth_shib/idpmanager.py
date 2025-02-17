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
from urllib.parse import urlencode

from django.conf import settings

from openstack_dashboard.api import keystone as keystone_api
from keystone.federation import utils as federation_utils


LOG = logging.getLogger(__name__)

class Federated_Account:

    entity_table = getattr(settings, 'WEBSSO_IDP_ENTITIES', {})
    mapping_table = getattr(settings, 'WEBSSO_IDP_MAPPING', {})
    rule_table = getattr(settings, 'WEBSSO_IDP_RULES', {})

    idp_equiv = getattr(settings, 'IDP_EQUIV', {
        'studenti.unipd.it' : 'unipd.it'
    })

    def __init__(self, request):

        self.root_url = request.META['SCRIPT_NAME']

        if 'Shib-Identity-Provider' in request.META:

            self.idpid = request.META['Shib-Identity-Provider']

            self.username = request.META['REMOTE_USER']
            idx = request.META['REMOTE_USER'].find('@')
            tmp_prov = request.META['REMOTE_USER'][idx+1:] if idx > 0 else 'Unknown'
            self.provider = Federated_Account.idp_equiv.get(tmp_prov, tmp_prov)

        elif 'OIDC-iss' in request.META:
            self.username = None
            self.idpid = request.META['OIDC-iss']
            self.provider = request.META.get('OIDC-organisation_name', 'Unknown')
            self.username = None
        else:
            self.username = None
            self.idpid = None
            self.provider = None

        if self.idpid and not self.username:
            step1 = list(x for x in Federated_Account.entity_table.items()
                         if self.idpid in x[1])
            if len(step1) > 0:
                step2 = list(x for x in Federated_Account.mapping_table.items()
                             if step1[0][0] == x[1][0])
                if len(step2) > 0:
                    rules = Federated_Account.rule_table.get(step2[0][0], [])

                    try:
                        ruleproc = federation_utils.RuleProcessor(step2[0][0], rules)
                        res = ruleproc.process(request.META)
                        if res and 'user' in res:
                            self.username = res['user']['name']
                            LOG.debug("Found account: %s" % self.username)
                        else:
                            LOG.debug("No rule for %s" % step2[0][0])
                    except Exception as exc:
                        LOG.debug(str(exc), exc_info=True)
                else:
                    LOG.debug("No mapping for %s" % step1[0][0])
            else:
                LOG.debug("No identity provider for %s" % self.idpid)

        self.email = None
        for m_item in ['mail', 'OIDC-email']:
            if m_item in request.META:
                self.email = request.META[m_item].split(';')[0]
                break

        self.givenname = None
        for gn_item in ['givenName', 'OIDC-given_name']:
            if gn_item in request.META:
                self.givenname = request.META[gn_item]
                break

        self.sn = None
        for sn_item in ['sn', 'OIDC-family_name']:
            if sn_item in request.META:
                self.sn = request.META[sn_item]
                break

    def __bool__(self):
        return self.username != None

def get_logout_url(request, *args):

    tmpu = 'https://%s:%s' % (
        request.META['SERVER_NAME'],
        request.META['SERVER_PORT']
    )
    tmpu += args[0] if len(args) else '/dashboard'

    if 'Shib-Identity-Provider' in request.META:
        return '/Shibboleth.sso/Logout?%s' % urlencode({ 'return' : tmpu })

    if 'OIDC-iss' in request.META:
        redir_path = getattr(settings, 'OIDC_REDIRECT_PATH', 
                             request.META['SCRIPT_NAME'] + '/redirect-uri')
        return '%s?%s' % (redir_path, urlencode({ 'logout' : tmpu }))

    return None

def postproc_logout(request, response):
    # for any further customizations
    return response


def checkFederationSetup(request):

    if not getattr(settings, 'CHECK_FEDERATION_SETUP', False):
        return

    mapping_table = getattr(settings, 'WEBSSO_IDP_MAPPING', {})
    entity_table = getattr(settings, 'WEBSSO_IDP_ENTITIES', {})
    rule_table = getattr(settings, 'WEBSSO_IDP_RULES', {})
    
    try:
        tmp_table = entity_table.copy()
        for idp_item in keystone_api.identity_provider_list(request):
            tmp_table.pop(idp_item.id, None)
            LOG.debug("Found provider %s" % idp_item.id)

        for idp_id in tmp_table:
            keystone_api.identity_provider_create(request, idp_id, None, True, 
                                                  tmp_table.get(idp_id, []))
            LOG.debug("Created provider %s" % idp_id)
    except:
        LOG.error("Cannot setup identity providers", exc_info=True)
    

    try:
        for map_item in keystone_api.mapping_list(request):
            rule_table.pop(map_item.id, None)
            LOG.debug("Found mapping %s" % map_item.id)

        for map_id in rule_table:
            keystone_api.mapping_create(request, map_id, rule_table.get(map_id, []))
            LOG.debug("Created mapping %s" % map_id)
    except:
        LOG.error("Cannot setup rules", exc_info=True)

    try:
        for map_id in mapping_table:
            idp_id, proto_id = mapping_table[map_id]
            missing = True
            for proto_item in keystone_api.protocol_list(request, idp_id):
                if proto_item.mapping_id == map_id:
                    LOG.debug("Found protocol %s" % map_id)
                    missing = False
                    break

            if missing:
                keystone_api.protocol_create(request, proto_id, idp_id, map_id)
                LOG.debug("Found protocol %s %s" % (proto_id, map_id))
    except:
        LOG.error("Cannot setup protocols", exc_info=True)

