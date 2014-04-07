from django.conf import settings
from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.project import dashboard

TENANTADMIN_ROLE = getattr(settings, 'TENANTADMIN_ROLE', 'project_manager')

class SubscriptionManager(horizon.Panel):
    name = _("Subscriptions")
    slug = 'subscription_manager'
    permissions = ('openstack.roles.%s' % TENANTADMIN_ROLE,)

dashboard.Project.register(SubscriptionManager)
