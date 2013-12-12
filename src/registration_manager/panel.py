
from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.admin import dashboard

class RegisterManager(horizon.Panel):
    name = _("Registrations")
    slug = 'registration_manager'

dashboard.Admin.register(RegisterManager)
