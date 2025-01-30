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

from datetime import datetime
from datetime import timezone

from django.db import transaction
from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.forms.widgets import SelectDateWidget
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_variables

from horizon import forms
from horizon import exceptions
from horizon import messages

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import PSTATUS_ADM_ELECT
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import PSTATUS_RENEW_ATTEMPT
from openstack_auth_shib.models import PSTATUS_RENEW_DISC
from openstack_auth_shib.models import PSTATUS_ADM_ELECT
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import USER_RENEWED_TYPE
from openstack_auth_shib.notifications import GENERIC_MESSAGE
from openstack_auth_shib.notifications import CHANGED_MEMBER_ROLE
from openstack_auth_shib.notifications import PROMO_AVAIL
from openstack_auth_shib.utils import DEFAULT_ROLEID
from openstack_auth_shib.utils import TENANTADMIN_ROLE
from openstack_auth_shib.utils import TENANTADMIN_ROLEID

from openstack_dashboard.api.keystone import keystoneclient as client_factory

LOG = logging.getLogger(__name__)

try:
    MAX_RENEW = int(getattr(settings, 'TENANT_MAX_RENEW', '4'))
except:
    MAX_RENEW = 4

class ModifyExpForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ModifyExpForm, self).__init__(request, *args, **kwargs)

        self.fields['userid'] = forms.CharField(widget=HiddenInput)
        
        curr_year = datetime.now(timezone.utc).year
        years_list = list(range(curr_year, curr_year + MAX_RENEW))           
        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            required=True,
            widget=SelectDateWidget(None, years_list)
        )

    def clean(self):
        data = super(ModifyExpForm, self).clean()

        now = datetime.now(timezone.utc)
        if data['expiration'].date() < now.date():
            raise ValidationError(_('Invalid expiration time.'))
        if data['expiration'].year > now.year + MAX_RENEW:
            raise ValidationError(_('Invalid expiration time.'))

        if data['userid'] == self.request.user.id:
            raise ValidationError(_('Invalid operation.'))

        q_args = {
            'registration__userid' : data['userid'],
            'project__projectid' : self.request.user.tenant_id
        }
        if PrjRole.objects.filter(**q_args).count() > 0:
            raise ValidationError(_('Cannot change expiration for a project admin'))

        return data

    @sensitive_variables('data')
    def handle(self, request, data):
        try:

            with transaction.atomic():

                q_args = {
                    'registration__userid' : data['userid'],
                    'project__projectid' : request.user.tenant_id
                }
                PrjRequest.objects.filter(**q_args).delete()

                q_args['expdate'] = data['expiration']
                Expiration.objects.update_expiration(**q_args)

                tmpres = EMail.objects.filter(registration__userid=data['userid'])
                if len(tmpres) == 0:
                    return True

                user_name = tmpres[0].registration.username
                user_mail = tmpres[0].email
                noti_params = {
                    'username' : user_name,
                    'project' : request.user.tenant_name,
                    'expiration' : data['expiration'].strftime("%d %B %Y")
                }

                try:
                    notifyUser(request=request, rcpt=user_mail, action=USER_RENEWED_TYPE,
                               context=noti_params, dst_user_id=data['userid'])
                    notifyAdmin(request=request, action=USER_RENEWED_TYPE, context=noti_params)
                except:
                    LOG.error("Cannot notify %s" % user_name, exc_info=True)

        except:
            LOG.error("Error changing expiration date", exc_info=True)
            messages.error(request, _("Cannot change expiration date"))
            return False
        return True

class DemoteUserForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(DemoteUserForm, self).__init__(request, *args, **kwargs)

        self.fields['userid'] = forms.CharField(widget=HiddenInput)

    def clean(self):
        if not TENANTADMIN_ROLE in [ r['name'] for r in self.request.user.roles ]:
            raise ValidationError(_("Not authorized for demoting users"))

        return super(DemoteUserForm, self).clean()

    @sensitive_variables('data')
    def handle(self, request, data):
        try:
            with transaction.atomic():
                registration = Registration.objects.get(userid = data['userid'])

                tmpres = EMail.objects.filter(registration__userid = data['userid'])
                member_email = tmpres[0].email if tmpres else None

                tmpres = EMail.objects.filter(registration__userid = request.user.id)
                admin_email = tmpres[0].email if tmpres else None

                PrjRole.objects.filter(
                    registration = registration,
                    project__projectname = request.user.tenant_name
                ).delete()

                roles_obj = client_factory(request).roles
                role_assign_obj = client_factory(request).role_assignments

                missing_default = True
                for r_item in role_assign_obj.list(project = request.user.tenant_id,
                                                   user = data['userid']):
                    if r_item.role['id'] == DEFAULT_ROLEID:
                        missing_default = False

                if missing_default:
                    roles_obj.grant(DEFAULT_ROLEID,
                        project = request.user.tenant_id, user = data['userid'])

                roles_obj.revoke(TENANTADMIN_ROLEID,
                    project = request.user.tenant_id, user = data['userid'])                    

            noti_params = {
                'admin_address' : admin_email,
                'project' : request.user.tenant_name,
                's_role' : _('Project manager'),
                'd_role' : _('Project user')
            }
            notifyUser(request = request, rcpt = member_email,
                       action = CHANGED_MEMBER_ROLE, context = noti_params,
                       dst_project_id = request.user.project_id,
                       dst_user_id = data['userid'])
        except:
            LOG.error("Error demoting user", exc_info=True)
            messages.error(request, _("Cannot demote user"))
            return False
        return True

class ProposeAdminForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ProposeAdminForm, self).__init__(request, *args, **kwargs)

        self.fields['userid'] = forms.CharField(widget=HiddenInput)

    @sensitive_variables('data')
    def handle(self, request, data):
        try:
            with transaction.atomic():

                registration = Registration.objects.get(userid = data['userid'])
                project = Project.objects.get(projectname = request.user.tenant_name)
                q_args = {
                    'registration' : registration,
                    'project' : project,
                    'flowstatus__in' : [
                        PSTATUS_ADM_ELECT,
                        PSTATUS_RENEW_MEMB,
                        PSTATUS_RENEW_ATTEMPT,
                        PSTATUS_RENEW_DISC
                    ]
                }
                banned_status = [ x.flowstatus for x in PrjRequest.objects.filter(**q_args) ]
                if PSTATUS_ADM_ELECT in banned_status:
                    messages.error(request, _('Promotion has already been sent.'))
                    return True
                if len(banned_status) > 0:
                    messages.error(request, _('Unable to propose the administrator: user is going to expire.'))
                    return True

                PrjRequest(
                    registration = registration,
                    project = project,
                    flowstatus = PSTATUS_ADM_ELECT,
                    notes = ""
                ).save()
                
                noti_params = {
                    'username' : registration.username,
                    'project' : project.projectname
                }
                notifyAdmin(request = request, action = PROMO_AVAIL, context = noti_params)

        except:
            LOG.error("Error proposing admin", exc_info=True)
            messages.error(request, _("Cannot propose administrator"))
            return False
        return True


class SendMsgForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(SendMsgForm, self).__init__(request, *args, **kwargs)

        self.fields['message'] = forms.CharField(
            label=_('Message'),
            required=True,
            widget=forms.widgets.Textarea()
        )

    @sensitive_variables('data')
    def handle(self, request, data):
        try:
            with transaction.atomic():
                q_args = {
                    'project__projectid' : self.request.user.tenant_id
                }
                tmpl = [ x.registration for x in Expiration.objects.filter(**q_args) ]
                e_addresses = [ x.email for x in EMail.objects.filter(registration__in = tmpl) ]
                noti_params = {
                    'username' : self.request.user.username,
                    'project' : self.request.user.tenant_name,
                    'message' : data['message']
                }
                notifyUser(request=request, rcpt=e_addresses, action=GENERIC_MESSAGE,
                           context=noti_params, dst_user_id=self.request.user.id)
        except:
            exceptions.handle(request)
            return False
        return True




