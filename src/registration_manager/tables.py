import logging

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from openstack_auth_shib.models import Registration, RegRequest

from horizon import tables

LOG = logging.getLogger(__name__)

class ProcessLink(tables.LinkAction):
    name = "reqprocess"
    verbose_name = _("Process")
    url = "horizon:admin:registration_manager:process"
    classes = ("ajax-modal", "btn-edit")

class RegisterTable(tables.DataTable):
    regid = tables.Column('regid', verbose_name=_('ID'))
    username = tables.Column('username', verbose_name=_('User name'))
    fullname = tables.Column('fullname', verbose_name=_('Full name'))
    domain = tables.Column('domain', verbose_name=_('Domain'))
    region = tables.Column('region', verbose_name=_('Region'))

    class Meta:
        name = "register_table"
        verbose_name = _("Registrations")
        row_actions = (ProcessLink, )

    def get_object_id(self, datum):
        return datum.regid





