
import logging
import base64

from Crypto.Cipher import AES

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from keystoneclient import exceptions as keystone_exceptions
from keystoneclient.v3.client import Client as BaseClient

from openstack_auth import backend as base_backend
from openstack_auth.exceptions import KeystoneAuthException
from openstack_auth.user import create_user_from_token
from openstack_auth.user import Token
from openstack_auth.utils import get_keystone_version


LOG = logging.getLogger(__name__)


class ExtClient(BaseClient):

    def __init__(self, **kwargs):
        if 'secret_token' in kwargs:
            self.secret_token = kwargs['secret_token']
            del kwargs['secret_token']
        else:
            self.secret_token = None
        super(ExtClient, self).__init__(**kwargs)

    def _do_auth(self, auth_url, user_id=None, username=None,
                 user_domain_id=None, user_domain_name=None, password=None,
                 domain_id=None, domain_name=None,
                 project_id=None, project_name=None, project_domain_id=None,
                 project_domain_name=None, token=None, trust_id=None):

        if self.secret_token == None:
            return super(ExtClient, self)._do_auth(auth_url, user_id, username,
                                                   user_domain_id, user_domain_name,
                                                   password, domain_id, domain_name,
                                                   project_id, project_name,
                                                   project_domain_id,
                                                   project_domain_name, token,
                                                   trust_id)
        headers = {}
        if auth_url is None:
            raise ValueError("Cannot authenticate without a valid auth_url")
        url = auth_url + "/auth/tokens"
        body = {'auth': {'identity': {}}}
        ident = body['auth']['identity']
        
        headers['X-Auth-Secret'] = self.secret_token
        ident['methods'] = ['sKey']
        ident['sKey'] = {}
        

        resp, body = self.request(url, 'POST', body=body, headers=headers)
        return resp, body





#
# Register this backend in /usr/share/openstack-dashboard/openstack_dashboard/settings.py
# AUTHENTICATION_BACKENDS = ('openstack_auth_shib.backend.ExtKeystoneBackend',)
#
class ExtKeystoneBackend(base_backend.KeystoneBackend):

    def authenticate(self, request=None, username=None, password=None,
                     user_domain_name=None, auth_url=None):
        
        if password:
            parentObj = super(ExtKeystoneBackend, self)
            return parentObj.authenticate(request, username, password,
                                          user_domain_name, auth_url)

        LOG.debug('Beginning user authentication for user "%s".' % username)

        insecure = getattr(settings, 'OPENSTACK_SSL_NO_VERIFY', False)
        secret_key = getattr(settings, 'SECRET_KEY', None)
        
        # TODO missing IV
        cipher = AES.new(secret_key, AES.MODE_CFB)
        fqun = "%s@%s" % (username, user_domain_name)
        secret_token = base64.b64encode(cipher.encrypt(fqun))

        try:
            client = ExtClient(user_domain_name=user_domain_name,
                               username=username,
                               secret_token=secret_token,
                               auth_url=auth_url,
                               insecure=insecure,
                               debug=settings.DEBUG)

            unscoped_auth_ref = client.auth_ref
            unscoped_token = Token(auth_ref=unscoped_auth_ref)
            
            # Force API V3
            if get_keystone_version() < 3:
                unscoped_token.serviceCatalog = unscoped_auth_ref.get('catalog', [])
                unscoped_token.roles = unscoped_auth_ref.get('roles', [])
            
        except (keystone_exceptions.Unauthorized,
                keystone_exceptions.Forbidden,
                keystone_exceptions.NotFound) as exc:
            msg = _('Invalid user name or password.')
            LOG.debug(exc.message)
            raise KeystoneAuthException(msg)
        except (keystone_exceptions.ClientException,
                keystone_exceptions.AuthorizationFailure) as exc:
            msg = _("An error occurred authenticating. Please try again later.")
            LOG.debug(exc.message)
            raise KeystoneAuthException(msg)

        self.check_auth_expiry(unscoped_auth_ref)

        if unscoped_auth_ref.project_scoped:
            auth_ref = unscoped_auth_ref
        else:
            # For now we list all the user's projects and iterate through.
            try:
                client.management_url = auth_url
                projects = client.projects.list(user=unscoped_auth_ref.user_id)
            except (keystone_exceptions.ClientException,
                    keystone_exceptions.AuthorizationFailure) as exc:
                msg = _('Unable to retrieve authorized projects.')
                raise KeystoneAuthException(msg)

            # Abort if there are no projects for this user
            if not projects:
                msg = _('You are not authorized for any projects.')
                raise KeystoneAuthException(msg)

            while projects:
                project = projects.pop()
                try:
                    client = keystone_client.Client(
                        tenant_id=project.id,
                        token=unscoped_auth_ref.auth_token,
                        auth_url=auth_url,
                        insecure=insecure,
                        debug=settings.DEBUG)
                    auth_ref = client.auth_ref
                    break
                except (keystone_exceptions.ClientException,
                        keystone_exceptions.AuthorizationFailure):
                    auth_ref = None

            if auth_ref is None:
                msg = _("Unable to authenticate to any available projects.")
                raise KeystoneAuthException(msg)

            # Check expiry for our new scoped token.
            self.check_auth_expiry(auth_ref)

        # If we made it here we succeeded. Create our User!
        
        # Force API V3
        project_token = Token(auth_ref)
        if get_keystone_version() < 3:
            project_token.serviceCatalog = auth_ref.get('catalog', [])
            project_token.roles = auth_ref.get('roles', [])
        
        user = create_user_from_token(request,
                                      project_token,
                                      client.service_catalog.url_for())

        if request is not None:
            request.session['unscoped_token'] = unscoped_token.id
            request.user = user

            # Support client caching to save on auth calls.
            setattr(request, base_backend.KEYSTONE_CLIENT_ATTR, client)

        LOG.debug('Authentication completed for user "%s".' % username)
        return user

