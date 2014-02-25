from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.settings import dashboard


class PasswordPanel(horizon.Panel):
    name = _("Activate Password")
    slug = 'password_manager'

dashboard.Settings.register(PasswordPanel)

