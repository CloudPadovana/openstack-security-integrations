
from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.project import dashboard
from openstack_auth_shib.models import TENANTADMIN_ROLE

class SubscriptionManager(horizon.Panel):
    name = _("Subscriptions")
    slug = 'subscription_manager'
    permissions = ('openstack.roles.%s' % TENANTADMIN_ROLE,)

dashboard.Project.register(SubscriptionManager)
