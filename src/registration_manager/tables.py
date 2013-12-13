import logging

from django.utils.translation import ugettext_lazy as _

from openstack_auth_shib.models import Candidate

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
        LOG.debug("Discarding registration for %s" % obj_id)
        Candidate.objects.filter(uname=obj_id).delete()


class RegisterTable(tables.DataTable):
    uname = tables.Column('uname', verbose_name=_('User Name'))
    domain = tables.Column('domain', verbose_name=_('Domain'))
    project = tables.Column('project', verbose_name=_('Project'))

    class Meta:
        name = "register_table"
        verbose_name = _("Registrations")
        row_actions = (ApproveLink, DiscardAction,)
        table_actions = (DiscardAction,)

    def get_object_id(self, datum):
        return datum.uname

