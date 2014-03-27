import logging

from django.db import transaction
from django.utils.translation import ugettext as _

from horizon import tables

from openstack_dashboard.dashboards.admin.users.tables import UsersTable as BaseUsersTable
from openstack_dashboard.dashboards.admin.users.tables import EditUserLink as BaseEditUserLink
from openstack_dashboard.dashboards.admin.users.tables import ToggleEnabled
from openstack_dashboard.dashboards.admin.users.tables import DeleteUsersAction as BaseDeleteUsersAction
from openstack_dashboard.dashboards.admin.users.tables import UserFilterAction

from openstack_auth_shib.models import Registration

LOG = logging.getLogger(__name__)

class EditUserLink(BaseEditUserLink):
    url = "horizon:admin:user_manager:update"

class DeleteUsersAction(BaseDeleteUsersAction):

    def delete(self, request, obj_id):
    
        with transaction.commit_on_success():
            tmp_list = Registration.objects.filter(userid=obj_id)
            if len(tmp_list):
                tmp_list[0].delete()
            super(DeleteUsersAction, self).delete(request, obj_id)

class RenewLink(tables.LinkAction):
    name = "renewexp"
    verbose_name = _("Renew Expiration")
    url = "horizon:admin:user_manager:renew"
    classes = ("ajax-modal", "btn-edit")

class UsersTable(BaseUsersTable):

    expiration = tables.Column('expiration', verbose_name=_('Expiration date'))

    class Meta:
        name = "user_table"
        verbose_name = _("Users")
        row_actions = (
            EditUserLink,
            ToggleEnabled,
            RenewLink,
            DeleteUsersAction
        )
        table_actions = (UserFilterAction, DeleteUsersAction)

