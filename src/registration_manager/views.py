import logging

from django.utils.translation import ugettext_lazy as _

from horizon import tables
from horizon import exceptions

from openstack_auth_shib.models import Candidate

LOG = logging.getLogger(__name__)

class DiscardAction(tables.DeleteAction):
    data_type_singular = _("Registration")
    data_type_plural = _("Registrations")
    #policy_rules = (("identity", "identity:delete_role"),)

    def allowed(self, request, role):
        return True

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
        row_actions = (DiscardAction,)
        table_actions = (DiscardAction,)

    def get_object_id(self, datum):
        return datum.uname

class IndexView(tables.DataTableView):
    table_class = RegisterTable
    template_name = 'admin/registration_manager/reg_manager.html'

    def get_data(self):
    
        reg_list = []
        
        try:
            reg_list = Candidate.objects.all()
        except Exception:
            exceptions.handle(self.request, _('Unable to retrieve registration list.'))

        return reg_list

