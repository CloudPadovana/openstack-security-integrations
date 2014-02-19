import logging

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from horizon import tables

LOG = logging.getLogger(__name__)

class ApproveLink(tables.LinkAction):
    name = "approve"
    verbose_name = _("Approve")
    url = "horizon:project:subscription_manager:approve"
    classes = ("ajax-modal", "btn-edit")

class SubscriptionTable(tables.DataTable):
    username = tables.Column('username', verbose_name=_('User name'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    notes = tables.Column('notes', verbose_name=_('Notes'))

    class Meta:
        name = "subscription_table"
        verbose_name = _("Subscriptions")
        row_actions = (ApproveLink,)
        table_actions = ()

    def get_object_id(self, datum):
        return datum.regid





