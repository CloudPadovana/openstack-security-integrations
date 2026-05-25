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
HORIZON_CONFIG['privacy_page'] = 'https://cloudveneto.it/privacy-statement/'

USER_MENU_LINKS = [
    {
        'name': _('Privacy statement'),
        'icon_classes': ['fa-question-circle', ],
        'external' : True,
        'url' : HORIZON_CONFIG['privacy_page']
    },
    {
        'name': _('OpenStack RC File'),
        'icon_classes': ['fa-download', ],
        'url': 'horizon:project:api_access:openrc',
    }
]

AVAILABLE_THEMES.append(( 'cap', pgettext_lazy("CloudVeneto theme", "CAP"), 'themes/cap' ))

DEFAULT_THEME = 'cap'

DATABASES = {}

# Bind Horizon <-> Keystone for each point of access
HORIZON_CONFIG['srv_bind_table'] = {}

HORIZON_CONFIG['course_for'] = {}

HORIZON_CONFIG['new_splash'] = False

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "openstack_auth_shib.utils.CloudVenetoPwdValidator",
        "OPTIONS": { "min_length": 10, },
    }
]

