from django.utils.translation import ugettext_lazy as _

from horizon import tables

class RegisterTable(tables.DataTable):
    uname = tables.Column('username', verbose_name=_('User Name'))
    domain = tables.Column('domain', verbose_name=_('Domain'))
    project = tables.Column('project', verbose_name=_('Project'))

    class Meta:
        name = "register_table"
        verbose_name = _("Registrations")


class IndexView(tables.DataTableView):
    table_class = RegisterTable
    template_name = 'admin/registration_manager/reg_manager.html'

    def get_data(self):
        return []

