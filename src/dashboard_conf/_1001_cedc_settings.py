HORIZON_CONFIG['help_url'] = 'https://cloud.cedc.csia.unipd.it/User_Guide/index.html'

AVAILABLE_THEMES.append(( 'cedc', pgettext_lazy("Cloud Veneto", "CED-C"), 'themes/cedc' ))

DEFAULT_THEME = 'cedc'

HORIZON_CONFIG['identity_providers'].append(
    {
      'id' :          'infn_sso',
      'context' :     '/dashboard-infn',
      'path' :        '/dashboard-infn/auth/register/',
      'description' : 'INFN AAI',
      'logo' :        '/dashboard/static/dashboard/img/logoInfnAAI.png'
    }
)

HORIZON_CONFIG['identity_providers'].append(
    { 
      'id' :          'unipd_sso',
      'context' :     '/dashboard-unipd',
      'path' :        '/dashboard-unipd/auth/register/',
      'description' : 'UniPD IdP',
      'logo' :        '/dashboard/static/dashboard/img/logoUniPD.png'
    }
)

WEBSSO_IDP_MAPPING["infn_sso"] = ("infnaai", "mapped")
WEBSSO_IDP_MAPPING["unipd_sso"] = ("unipdaai", "mapped")

WEBSSO_IDP_ENTITIES["infnaai"] = [ "https://idp.infn.it/saml2/idp/metadata.php" ]
WEBSSO_IDP_RULES["infn_sso"] = [
    {
        "local": [
            {
                "user": {
                    "name": "{0}",
                    "domain": { "id": "default" },
                    "type": "local"
                }
                
            }
        ],
        "remote": [ { "type": "eppn" } ]
    }
]


WEBSSO_IDP_ENTITIES["unipdaai"] = [ "https://shibidp.cca.unipd.it/idp/shibboleth" ]
WEBSSO_IDP_RULES["unipd_sso"] = [
    {
        "local": [
            {
                "user": {
                    "name": "{0}",
                    "domain": { "id": "default" },
                    "type": "local"
                }
                
            }
        ],
        "remote": [ { "type": "eppn" } ]
    }
]


WEBSSO_CHOICES = WEBSSO_CHOICES + (('infn_sso', 'INFN AAI'), ('unipd_sso', 'UniPD IdP'),)

