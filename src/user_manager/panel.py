from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.admin import dashboard

class UserManager(horizon.Panel):
    name = _("Users")
    slug = 'user_manager'

dashboard.Admin.register(UserManager)
