HORIZON_CONFIG['help_url'] = 'http://www.pd.infn.it/cloud/Users_Guide/html-desktop/'

AVAILABLE_THEMES.append(( 'cap', pgettext_lazy("Cloud Area Padovana theme", "CAP"), 'themes/cap' ))

DEFAULT_THEME = 'cap'

HORIZON_CONFIG['identity_providers'].append(
    {
      'context' : '/dashboard-infn',
      'path' : '/dashboard-infn/auth/login/',
      'description' : 'INFN AAI',
      'logo' : '/dashboard/static/dashboard/img/logoInfnAAI.png'
    }
)

