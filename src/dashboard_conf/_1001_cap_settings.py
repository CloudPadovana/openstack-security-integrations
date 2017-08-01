HORIZON_CONFIG['help_url'] = 'http://www.pd.infn.it/cloud/Users_Guide/html-desktop/'

AVAILABLE_THEMES.append(( 'cap', pgettext_lazy("Cloud Area Padovana theme", "CAP"), 'themes/cap' ))

DEFAULT_THEME = 'cap'

HORIZON_CONFIG['identity_providers'].append(
    {
      'id' :          'infn_sso',
      'context' :     '/dashboard-infn',
      'path' :        '/dashboard-infn/auth/register/',
      'description' : 'INFN AAI',
      'logo' :        '/dashboard/static/dashboard/img/logoInfnAAI.png'
    }
)

WEBSSO_IDP_MAPPING["infn_sso"] = ("infnaai", "mapped")
WEBSSO_CHOICES = WEBSSO_CHOICES + (('infn_sso', 'INFN AAI'),)

