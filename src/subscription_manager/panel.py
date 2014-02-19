
from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.project import dashboard

class SubscriptionManager(horizon.Panel):
    name = _("Subscriptions")
    slug = 'subscription_manager'
    permissions = ('openstack.roles.project_manager',)

dashboard.Project.register(SubscriptionManager)
