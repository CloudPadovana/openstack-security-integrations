import logging

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy

from horizon import exceptions

from openstack_dashboard.dashboards.admin.users.views import IndexView as BaseIndexView
from openstack_dashboard.dashboards.admin.users.views import UpdateView as BaseUpdateView
from openstack_dashboard.dashboards.admin.users.views import CreateView as BaseCreateView

from openstack_dashboard import api

from .tables import UsersTable

LOG = logging.getLogger(__name__)


class IndexView(BaseIndexView):
    table_class = UsersTable
    template_name = 'admin/user_manager/index.html'

class UpdateView(BaseUpdateView):
    template_name = 'admin/user_manager/update.html'
    success_url = reverse_lazy('horizon:admin:user_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                self._object = api.keystone.user_get(self.request,
                                                     self.kwargs['user_id'],
                                                     admin=True)
            except Exception:
                redirect = reverse_lazy('horizon:admin:user_manager:index')
                exceptions.handle(self.request, _('Unable to update user.'),
                                  redirect=redirect)
        return self._object

class CreateView(BaseCreateView):
    template_name = 'admin/user_manager/create.html'
    success_url = reverse_lazy('horizon:admin:user_manager:index')

