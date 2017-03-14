HORIZON_CONFIG['user_home'] = 'openstack_auth_shib.utils.get_user_home'

AUTHENTICATION_PLUGINS = [
    'openstack_auth_shib.backend.SKeyPluginFactory',
    'openstack_auth.plugin.password.PasswordPlugin',
    'openstack_auth.plugin.token.TokenPlugin'
]

AUTHENTICATION_URLS = ['openstack_auth_shib.urls']

INSTALLED_APPS.append('openstack_auth_shib')

NOTIFICATION_TEMPLATE_DIR = '/etc/openstack-auth-shib/notifications'

HORIZON_CONFIG['identity_providers'] = []

#KEYSTONE_SECRET_KEY = ""

#DATABASES = {
#    'default': {
#        'ENGINE' : 'django.db.backends.mysql',
#        'NAME' : '',
#        'USER' : '',
#        'PASSWORD' : '',
#        'HOST' : '',
#        'PORT' : '3306'
#    }
#}

