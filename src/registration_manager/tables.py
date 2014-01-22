import logging

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from openstack_auth_shib.models import Registration, RegRequest

from horizon import tables

LOG = logging.getLogger(__name__)

class ApproveLink(tables.LinkAction):
    name = "approve"
    verbose_name = _("Approve")
    url = "horizon:admin:registration_manager:approve"
    classes = ("ajax-modal", "btn-edit")

class DiscardAction(tables.DeleteAction):
    data_type_singular = _("Registration")
    data_type_plural = _("Registrations")

    def delete(self, request, obj_id):
    
        with transaction.commit_on_success():
            LOG.debug("Discarding registration for %d" % obj_id)
            Registration.objects.get(regid=obj_id).delete()
            #
            # TODO send notification via mail
            #


class RegisterTable(tables.DataTable):
    regid = tables.Column('regid', verbose_name=_('ID'))
    username = tables.Column('username', verbose_name=_('User name'))
    email = tables.Column('email', verbose_name=_('Email address'))
    notes = tables.Column('notes', verbose_name=_('Notes'))
    externalid = tables.Column('externalid', verbose_name=_('External ID'))
    domain = tables.Column('domain', verbose_name=_('Domain'))
    region = tables.Column('region', verbose_name=_('Region'))

    class Meta:
        name = "register_table"
        verbose_name = _("Registrations")
        row_actions = (ApproveLink, DiscardAction,)
        table_actions = (DiscardAction,)

    def get_object_id(self, datum):
        return datum.getID()





