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

import base64
import json

from keystone import identity
from keystone.auth import AuthMethodHandler
from keystone.openstack.common import log as logging
from keystone.exception import Unauthorized, UserNotFound, NotFound

from Crypto.Cipher import AES
from Crypto import __version__ as crypto_version
if crypto_version.startswith('2.0'):
    from Crypto.Util import randpool
else:
    from Crypto import Random

from oslo.config import cfg

METHOD_NAME = 'sKey'

LOG = logging.getLogger(__name__)

#
# TODO
# investigate OTP libraries
# https://github.com/nathforge/pyotp
# investigate schema based on timestamp and originatorID
# originatorID is the uniqueID of the thread sending the request.
#
# move token in the body
#

class SecretKeyAuth(AuthMethodHandler):

    def __init__(self):
        cfg.CONF.register_opt(cfg.StrOpt('secret_key', default=None), group='skey')
        self.identity_api = identity.Manager()
        
        self.aes_key = cfg.CONF.skey.secret_key
        if len(self.aes_key) >= 32:
            self.aes_key = self.aes_key[:32]
        elif len(self.aes_key) >= 16:
            self.aes_key = self.aes_key[:16]
        elif len(self.aes_key) >= 8:
            self.aes_key = self.aes_key[:8]
        else:
            self.aes_key = None
    
    def _parse_cryptoken(self, data):
        if self.aes_key == None:
            raise Exception("Wrong secret key")

        if crypto_version.startswith('2.0'):
            cipher = AES.new(self.aes_key, AES.MODE_CFB)
            b64msg = base64.b64decode(data)
            return cipher.decrypt(b64msg)[256:]
        
        prng = Random.new()
        iv = prng.read(16)
        cipher = AES.new(SECRET_KEY, AES.MODE_CFB, iv)
        b64msg = base64.b64decode(data)
        return cipher.decrypt(b64msg)[16:]
    
    def authenticate(self, context, auth_info, auth_context):
        
        if 'token' in auth_info and 'user_id' not in auth_context:
            try:
                
                userdata = json.loads(self._parse_cryptoken(auth_info['token']))
                if not 'username' in userdata or not 'domain' in userdata:
                    raise Unauthorized("Cannot retrieve user data")
                
                LOG.info("Accepted secret for user %s" % userdata['username'])
                
                uDict = self.identity_api.get_user_by_name(userdata['username'], userdata['domain'])
                dDict = self.identity_api.get_domain_by_name(userdata['domain'])
                
                if not uDict['enabled']:
                    raise Unauthorized("User %s is disabled" % uDict['name'])
                if not dDict['enabled']:
                    raise Unauthorized("Domain %s is disabled" % dDict['name'])
                
                auth_context['user_id'] = uDict['id']
                return None
                
            except UserNotFound:
                raise NotFound("Missing user")
            except Unauthorized as noAuthEx:
                LOG.error(str(noAuthEx))
                raise
            except Exception:
                LOG.error("Cannot decrypt token", exc_info=True)
        
        raise Unauthorized('Cannot authenticate using sKey')

'''
## Example of payload"

{"auth" : {"identity" : {"methods" : ["sKey"], "sKey" : { "token" : "DAnjHuV16dh4hXGCm/uk9A=="}}}}
'''


