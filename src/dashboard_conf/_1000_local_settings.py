HORIZON_CONFIG['user_home'] = 'openstack_auth_shib.utils.get_user_home'

AUTHENTICATION_URLS = ['openstack_auth_shib.urls']

INSTALLED_APPS.append('openstack_auth_shib')

NOTIFICATION_TEMPLATE_DIR = '/etc/openstack-auth-shib/notifications'

WEBSSO_ENABLED = True
WEBSSO_IDP_MAPPING = {}
WEBSSO_IDP_ENTITIES = {}
WEBSSO_IDP_RULES = {}
WEBSSO_CHOICES = (("credentials", "Keystone Credentials"),)

HORIZON_CONFIG['identity_providers'] = {}

HORIZON_CONFIG['help_url'] = 'http://userguide.cloudveneto.it/'

AVAILABLE_THEMES.append(( 'cap', pgettext_lazy("CloudVeneto theme", "CAP"), 'themes/cap' ))

DEFAULT_THEME = 'cap'

DATABASES = {}

# Bind Horizon <-> Keystone for each point of access
HORIZON_CONFIG['srv_bind_table'] = {}

HORIZON_CONFIG['course_for'] = {}

HORIZON_CONFIG['new_splash'] = False

