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

from oslo_log import log
from oslo_config import cfg

from keystone.auth.plugins import base
from keystone.common import dependency
from keystone.exception import Unauthorized, UserNotFound, NotFound

from Crypto.Cipher import AES
from Crypto import Random

METHOD_NAME = 'sKey'

LOG = log.getLogger(__name__)

@dependency.requires('identity_api')
class SecretKeyAuth(base.AuthMethodHandler):

    method = METHOD_NAME
    
    def __init__(self):
        super(SecretKeyAuth, self).__init__()
        cfg.CONF.register_opt(cfg.StrOpt('secret_key', default=None), group='skey')
        
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

        prng = Random.new()
        iv = prng.read(16)
        cipher = AES.new(self.aes_key, AES.MODE_CFB, iv)
        b64msg = base64.b64decode(data)
        return cipher.decrypt(b64msg)[16:]
    
    def authenticate(self, context, auth_info):
        
        if 'token' in auth_info:
            try:
                
                response_data = {}
                
                userdata = json.loads(self._parse_cryptoken(auth_info['token']))
                if not 'username' in userdata or not 'domain' in userdata:
                    raise Unauthorized("Cannot retrieve user data")
                
                LOG.info("Accepted secret for user %s" % userdata['username'])
                
                uDict = self.identity_api.get_user_by_name(userdata['username'], userdata['domain'])
                
                if not uDict['enabled']:
                    raise Unauthorized("User %s is disabled" % uDict['name'])
                
                response_data['user_id'] = uDict['id']
                return base.AuthHandlerResponse(status=True, response_body=None,
                                                response_data=response_data)
                
            except UserNotFound:
                raise NotFound("Missing user")
            except Unauthorized as noAuthEx:
                LOG.error(str(noAuthEx))
                raise
            except Exception:
                LOG.error("Cannot decrypt token", exc_info=True)
        
        raise Unauthorized('Cannot authenticate using sKey')



