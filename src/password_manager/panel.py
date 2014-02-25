from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.settings import dashboard

def enableActPwd(obj, context):
    request = context['request']
    if 'REMOTE_USER' in request.META and request.path.startswith('/dashboard-shib'):
        return True
    return False
    
class PasswordPanel(horizon.Panel):
    name = _("Activate Password")
    slug = 'password_manager'
#    nav = enableActPwd

dashboard.Settings.register(PasswordPanel)

