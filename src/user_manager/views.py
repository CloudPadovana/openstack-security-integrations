#  Copyright (c) 2014 INFN - "Istituto Nazionale di Fisica Nucleare" - Italy
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License. 

import logging
import datetime

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse_lazy

from horizon import forms
from horizon import exceptions
from horizon.utils import memoized

from openstack_dashboard.dashboards.identity.users import views as baseViews

from openstack_auth_shib.models import Expiration

from openstack_dashboard import api

from .tables import UsersTable
from .forms import RenewExpForm

LOG = logging.getLogger(__name__)

class IndexView(baseViews.IndexView):
    table_class = UsersTable
    template_name = 'idmanager/user_manager/index.html'

class UpdateView(baseViews.UpdateView):
    template_name = 'idmanager/user_manager/update.html'
    submit_url = "horizon:idmanager:user_manager:update"
    success_url = reverse_lazy('horizon:idmanager:user_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            try:
                self._object = api.keystone.user_get(self.request,
                                                     self.kwargs['user_id'],
                                                     admin=True)
            except Exception:
                redirect = reverse_lazy('horizon:idmanager:user_manager:index')
                exceptions.handle(self.request, _('Unable to update user.'),
                                  redirect=redirect)
        return self._object

class RenewView(forms.ModalFormView):
    form_class = RenewExpForm
    template_name = 'idmanager/user_manager/renewexp.html'
    success_url = reverse_lazy('horizon:idmanager:user_manager:index')

    def get_object(self):
        if not hasattr(self, "_object"):
            try:

                self._object = Expiration.objects.filter(registration__userid=self.kwargs['user_id'])

            except Exception:
                LOG.error("Renew error", exc_info=True)
                redirect = reverse_lazy('horizon:idmanager:user_manager:index')
                exceptions.handle(self.request, _('Unable to renew user.'),
                                  redirect=redirect)

        return self._object

    def get_context_data(self, **kwargs):
        context = super(RenewView, self).get_context_data(**kwargs)
        context['userid'] = self.kwargs['user_id']
        return context

    def get_initial(self):
    
        result = dict()
        result['userid'] = self.kwargs['user_id']
        
        for exp_item in self.get_object():
            result['prj_%s' % exp_item.project.projectname] = exp_item.expdate

        return result

class DetailView(baseViews.DetailView):
    template_name = 'idmanager/user_manager/detail.html'

    def get_redirect_url(self):
        return reverse_lazy('horizon:idmanager:user_manager:index')

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        table = UsersTable(self.request)
        context["actions"] = table.render_row_actions(self.get_data())
        return context

class ChangePasswordView(baseViews.ChangePasswordView):
    template_name = 'idmanager/user_manager/change_password.html'
    submit_url = 'horizon:idmanager:user_manager:change_password'
    success_url = reverse_lazy('horizon:idmanager:user_manager:index')

    @memoized.memoized_method
    def get_object(self):
        try:
            return api.keystone.user_get(self.request, self.kwargs['user_id'],
                                         admin=True)
        except Exception:
            redirect = reverse_lazy("horizon:idmanager:user_manager:index")
            exceptions.handle(self.request,
                              _('Unable to retrieve user information.'),
                              redirect=redirect)

