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

from horizon import forms
from horizon import exceptions

from django.db import transaction
from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.forms.extras.widgets import SelectDateWidget
from django.utils.translation import ugettext as _
from django.views.decorators.debug import sensitive_variables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB

from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import SUBSCR_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_NO_TYPE
from openstack_auth_shib.notifications import MEMBER_REMOVED
from openstack_auth_shib.notifications import USER_RENEWED_TYPE
from openstack_auth_shib.utils import TENANTADMIN_ROLE

from openstack_dashboard.api.keystone import keystoneclient as client_factory

from django.utils.translation import ugettext as _

LOG = logging.getLogger(__name__)

try:
    MAX_RENEW = int(getattr(settings, 'TENANT_MAX_RENEW', '4'))
except:
    MAX_RENEW = 4

class ApproveSubscrForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ApproveSubscrForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.CharField(widget=HiddenInput)

        curr_year = datetime.utcnow().year
        years_list = range(curr_year, curr_year + MAX_RENEW)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget(None, years_list)
        )

    def clean(self):
        data = super(ApproveSubscrForm, self).clean()
        now = datetime.utcnow()
        if data['expiration'].date() < now.date():
            raise ValidationError(_('Invalid expiration time.'))
        if data['expiration'].year > now.year + MAX_RENEW:
            raise ValidationError(_('Invalid expiration time.'))
        return data

    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
        
            role_names = [ role['name'] for role in self.request.user.roles ]
            if not TENANTADMIN_ROLE in role_names:
                raise Exception(_('Permissions denied: cannot approve subscriptions'))
        
            with transaction.atomic():
            
                curr_prjname = self.request.user.tenant_name
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectname' : curr_prjname
                }                
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                
                member_id = prj_req.registration.userid
                tmpres = EMail.objects.filter(registration__userid=member_id)
                member_email = tmpres[0].email if tmpres else None
                project_name = prj_req.project.projectname
                user_name = prj_req.registration.username
                
                LOG.debug("Approving subscription for %s" % prj_req.registration.username)
            
                default_role = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', None)
                
                expiration = Expiration()
                expiration.registration = prj_req.registration
                expiration.project = prj_req.project
                expiration.expdate = data['expiration']
                expiration.save()
                
                #
                # Update the max expiration per user
                #
                user_reg = prj_req.registration
                if data['expiration'] > user_reg.expdate:
                    user_reg.expdate = data['expiration']
                    user_reg.save()

                roles_obj = client_factory(request).roles
                arg_dict = {
                    'project' : prj_req.project.projectid,
                    'user' : prj_req.registration.userid
                }
                
                missing_default = True
                for item in roles_obj.list():
                    if item.name == default_role:
                        roles_obj.grant(item.id, **arg_dict)
                        missing_default = False
                if missing_default:
                    raise Exception("Default role is undefined")
                    
                #
                # clear request
                #
                prj_req.delete()

            #
            # send notification to the user
            #
            noti_params = {
                'username': user_name,
                'project' : project_name
            }

            notifyUser(request=self.request, rcpt=member_email, action=SUBSCR_OK_TYPE, context=noti_params,
                       dst_user_id=member_id)
        
        except:
            exceptions.handle(request)
            return False
            
        return True


class RejectSubscrForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(RejectSubscrForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.CharField(widget=HiddenInput)

        self.fields['reason'] = forms.CharField(
            label=_('Message'),
            required=False,
            widget=forms.widgets.Textarea()
        )


    @sensitive_variables('data')
    def handle(self, request, data):
    
        try:
        
            role_names = [ role['name'] for role in self.request.user.roles ]
            if not TENANTADMIN_ROLE in role_names:
                raise Exception(_('Permissions denied: cannot approve subscriptions'))
        
            with transaction.atomic():
            
                curr_prjname = self.request.user.tenant_name
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectname' : curr_prjname
                }                
                prj_req = PrjRequest.objects.filter(**q_args)[0]
                
                member_id = prj_req.registration.userid
                tmpres = EMail.objects.filter(registration__userid=member_id)
                member_email = tmpres[0].email if tmpres else None
                project_name = prj_req.project.projectname
                user_name = prj_req.registration.username
                
                #
                # clear request
                #
                prj_req.delete()

            #
            # send notification to the user
            #
            noti_params = {
                'username': user_name,
                'project' : project_name,
                'notes' : data['reason']
            }

            notifyUser(request=self.request, rcpt=member_email, action=SUBSCR_NO_TYPE, context=noti_params,
                       dst_user_id=member_id)
        
        except:
            exceptions.handle(request)
            return False
            
        return True


class RenewSubscrForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(RenewSubscrForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.CharField(widget=HiddenInput)

        curr_year = datetime.utcnow().year
        years_list = range(curr_year, curr_year + MAX_RENEW)

        self.fields['expiration'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget(None, years_list)
        )

    def clean(self):
        data = super(RenewSubscrForm, self).clean()
        now = datetime.utcnow()
        if data['expiration'].date() < now.date():
            raise ValidationError(_('Invalid expiration time.'))
        if data['expiration'].year > now.year + MAX_RENEW:
            raise ValidationError(_('Invalid expiration time.'))
        return data

    @sensitive_variables('data')
    def handle(self, request, data):

        try:
        
            with transaction.atomic():

                curr_prjname = self.request.user.tenant_name

                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectname' : curr_prjname,
                    'flowstatus' : PSTATUS_RENEW_MEMB
                }                
                prj_reqs = PrjRequest.objects.filter(**q_args)
                if len(prj_reqs) == 0:
                    return True
                
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectname' : curr_prjname
                }
                
                prj_exp = Expiration.objects.filter(**q_args)
                prj_exp.update(expdate=data['expiration'])
                
                #
                # Update the max expiration per user
                #
                user_reg = Registration.objects.get(regid=int(data['regid']))
                if data['expiration'] > user_reg.expdate:
                    user_reg.expdate = data['expiration']
                    user_reg.save()

                tmpres = EMail.objects.filter(registration=user_reg)
                user_mail = tmpres[0].email if len(tmpres) > 0 else None

                #
                # Clear requests
                #
                prj_reqs.delete()

            #
            # send notification to the user and cloud admin
            #
            noti_params = {
                'username' : user_reg.username,
                'project' : request.user.tenant_name,
                'expiration' : data['expiration'].strftime("%d %B %Y")
            }

            notifyUser(request=request, rcpt=user_mail, action=USER_RENEWED_TYPE,
                       context=noti_params, dst_user_id=user_reg.userid)
            notifyAdmin(request=request, action=USER_RENEWED_TYPE, context=noti_params)

        except:
            LOG.error("Cannot renew user", exc_info=True)
            exceptions.handle(request)
            return False
        
        return True


class DiscSubscrForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(DiscSubscrForm, self).__init__(request, *args, **kwargs)

        self.fields['regid'] = forms.CharField(widget=HiddenInput)

        self.fields['reason'] = forms.CharField(
            label=_('Message'),
            required=False,
            widget=forms.widgets.Textarea()
        )

    @sensitive_variables('data')
    def handle(self, request, data):

        try:
        
            with transaction.atomic():

                curr_prjname = self.request.user.tenant_name
                q_args = {
                    'registration__regid' : int(data['regid']),
                    'project__projectname' : curr_prjname,
                    'flowstatus' : PSTATUS_RENEW_MEMB
                }                
                prj_reqs = PrjRequest.objects.filter(**q_args)
                
                if len(prj_reqs) == 0:
                    return True

                user_id = prj_reqs[0].registration.userid

                tmpres = EMail.objects.filter(registration__userid=user_id)
                member_email = tmpres[0].email if tmpres else None
                member_name = prj_reqs[0].registration.username

                tmpres = EMail.objects.filter(registration__userid=request.user.id)
                admin_email = tmpres[0].email if tmpres else None

                #
                # Remove member from project
                #
                roles_obj = client_factory(request).roles
                role_assign_obj = client_factory(request).role_assignments
        
                arg_dict = {
                    'project' : request.user.tenant_id,
                    'user' : user_id
                }
                for r_item in role_assign_obj.list(**arg_dict):
                    roles_obj.revoke(r_item.role['id'], **arg_dict)
        
                #
                # Clear requests
                #
                prj_reqs.delete()

            #
            # Send notification to the user
            #
            noti_params = {
                'username' : member_name,
                'admin_address' : admin_email,
                'project' : request.user.tenant_name,
                'notes' : data['reason']
            }
            notifyUser(request=self.request, rcpt=member.email, action=MEMBER_REMOVED, context=noti_params,
                       dst_user_id=user_id)
                
        except:
            LOG.error("Cannot renew user", exc_info=True)
            exceptions.handle(request)
            return False
        
        return True


