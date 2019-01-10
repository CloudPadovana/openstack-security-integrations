HORIZON_CONFIG['help_url'] = 'http://www.pd.infn.it/cloud/Users_Guide/html-desktop/'

AVAILABLE_THEMES.append(( 'cap', pgettext_lazy("Cloud Area Padovana theme", "CAP"), 'themes/cap' ))

DEFAULT_THEME = 'cap'

HORIZON_CONFIG['identity_providers']['infn_sso'] = {
    'context' :     '/dashboard-infn',
    'path' :        '/dashboard-infn/auth/register/',
    'description' : 'INFN AAI',
    'logo' :        '/dashboard/static/dashboard/img/logoInfnAAI.png'
}

HORIZON_CONFIG['identity_providers']['unipd_sso'] = { 
    'context' :     '/dashboard-unipd',
    'path' :        '/dashboard-unipd/auth/register/',
    'description' : 'UniPD SSO',
    'logo' :        '/dashboard/static/dashboard/img/logoUniPD.png'
}

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

HORIZON_CONFIG['organization'] = {
    "infn.it" : [],
    "unipd.it" : [
        ("unipd-DFA", "Physics and Astronomy Dept."),
        ("unipd-DB", "Biology Dept."),
        ("unipd-GEO", "Geoscience Dept."),
        ("unipd-DEI", "Information Engineering Dept."),
        ("unipd-ICEA", "Civil and Environmental Engineering Dept."),
        ("unipd-MATH", "Mathematics Dept."),
        ("unipd-DMM", "Molecular Medicine Dept."),
        ("unipd-BIO", "Biomedical Sciences Dept."),
        ("unipd-DISC", "Chemical Sciences Dept."),
        ("unipd-DSF", "Pharmaceutical Sciences Dept.")
    ],
        "studenti.unipd.it" : [
        ("unipd-DFA", "Physics and Astronomy Dept."),
        ("unipd-DB", "Biology Dept."),
        ("unipd-GEO", "Geoscience Dept."),
        ("unipd-DEI", "Information Engineering Dept."),
        ("unipd-ICEA", "Civil and Environmental Engineering Dept."),
        ("unipd-MATH", "Mathematics Dept."),
        ("unipd-DMM", "Molecular Medicine Dept."),
        ("unipd-BIO", "Biomedical Sciences Dept."),
        ("unipd-DISC", "Chemical Sciences Dept."),
        ("unipd-DSF", "Pharmaceutical Sciences Dept.")
    ]

}

