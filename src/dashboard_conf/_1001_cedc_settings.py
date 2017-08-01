HORIZON_CONFIG['help_url'] = 'https://cloud.cedc.csia.unipd.it/User_Guide/index.html'

AVAILABLE_THEMES.append(( 'cedc', pgettext_lazy("Cloud Veneto", "CED-C"), 'themes/cedc' ))

DEFAULT_THEME = 'cedc'

HORIZON_CONFIG['identity_providers'].append(
    { 
      'id' :          'unipd_sso',
      'context' :     '/dashboard-unipd',
      'path' :        '/dashboard-unipd/auth/register/',
      'description' : 'UniPD IdP',
      'logo' :        '/dashboard/static/dashboard/img/logoUniPD.png'
    }
)

WEBSSO_IDP_MAPPING["unipd_sso"] = ("unipdaai", "mapped")
WEBSSO_CHOICES = WEBSSO_CHOICES + (('unipd_sso', 'UniPD IdP'),)

