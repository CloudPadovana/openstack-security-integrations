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

from django import http
from django.db import transaction
from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.forms.widgets import SelectDateWidget
from django.utils.translation import gettext as _

from horizon import forms
from horizon import messages

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PrjRole
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import UserMapping
from openstack_auth_shib.models import PSTATUS_PENDING
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import PSTATUS_RENEW_ATTEMPT
from openstack_auth_shib.models import PSTATUS_RENEW_DISC
from openstack_auth_shib.models import RSTATUS_REMINDER
from openstack_auth_shib.models import RSTATUS_REMINDACK
from openstack_auth_shib.models import RSTATUS_DISABLING
from openstack_auth_shib.models import RSTATUS_DISABLED
from openstack_auth_shib.models import RSTATUS_REENABLING
from openstack_auth_shib.models import PRJ_PRIVATE

from openstack_auth_shib.notifications import notifyProject
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import USER_RENEWED_TYPE
from openstack_auth_shib.notifications import SUBSCR_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_FORCED_OK_TYPE
from openstack_auth_shib.notifications import notifyAdmin
from openstack_auth_shib.notifications import MEMBER_REQUEST

from openstack_auth_shib.utils import get_year_list
from openstack_auth_shib.utils import DEFAULT_ROLEID

from openstack_dashboard.api import keystone as keystone_api
from openstack_dashboard.dashboards.identity.users import forms as baseForms

LOG = logging.getLogger(__name__)

class RenewExpForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):

        super(RenewExpForm, self).__init__(request, *args, **kwargs)

        self.fields['userid'] = forms.CharField(
            label=_("User ID"), 
            widget=HiddenInput
        )
        
        for item in kwargs['initial']:
            if item.startswith('n_prj_'):
                self.fields[item] = forms.DateTimeField(
                    label = "%s %s" % (_("Project"), item[6:]),
                    widget = SelectDateWidget(None, get_year_list())
                )
            elif item.startswith('a_prj_'):
                self.fields[item] = forms.DateTimeField(
                    label = "%s %s" % (_("Managed project"), item[6:]),
                    widget = SelectDateWidget(None, get_year_list()),
                    disabled = True
                )

    def clean(self):
        if not self.request.user.is_superuser:
            raise ValidationError(_("Operation not authorized"))

        return super(RenewExpForm, self).clean()

    def handle(self, request, data):

        mail_table = dict()
        exp_table = { x[6:] : data[x] for x in data if x.startswith('n_prj_') }

        with transaction.atomic():

            q_args = {
                'registration__userid' : data['userid'],
                'project__projectname__in' : list(exp_table.keys())
            }
            for exp_item in Expiration.objects.filter(**q_args):

                user_name = exp_item.registration.username
                prj_name = exp_item.project.projectname
                c_exp = exp_table.get(prj_name, None)

                if not c_exp or exp_item.expdate == c_exp:
                    continue

                q2_args = {
                    'registration__userid' : data['userid'],
                    'project__projectname' : prj_name,
                    'flowstatus__in' : [
                        PSTATUS_RENEW_ADMIN,
                        PSTATUS_RENEW_MEMB,
                        PSTATUS_RENEW_ATTEMPT,
                        PSTATUS_RENEW_DISC
                    ]
                }
                PrjRequest.objects.filter(**q2_args).delete()

                q2_args['expdate'] = c_exp
                Expiration.objects.update_expiration(**q2_args)

                if user_name not in mail_table:
                    tmpobj = EMail.objects.filter(registration__userid=data['userid'])
                    mail_table[user_name] = tmpobj[0].email if len(tmpobj) else None

                try:
                    noti_params = {
                        'username' : user_name,
                        'project' : prj_name,
                        'expiration' : c_exp.strftime("%d %B %Y")
                    }
                    notifyUser(request=request, rcpt=mail_table[user_name],
                               action=USER_RENEWED_TYPE,
                               context=noti_params, dst_user_id=data['userid'])
                except:
                    LOG.error("Cannot notify %s" % user_name, exc_info=True)

        return True

class UpdateUserForm(baseForms.UpdateUserForm):

    def __init__(self, request, *args, **kwargs):
        super(UpdateUserForm, self).__init__(request, *args, **kwargs)

    def clean(self):
        if not self.request.user.is_superuser:
            raise ValidationError(_("Operation not authorized"))

        return super(UpdateUserForm, self).clean()

    def handle(self, request, data):

        user_id = data['id']

        result = True
        try:
            with transaction.atomic():

                reg_usr = Registration.objects.filter(userid=user_id)[0]

                if "email" in data:
                    tmpres = EMail.objects.filter(registration=reg_usr)
                    tmpres.update(email=data['email'])

                if "name" in data and data['name'] != reg_usr.username:
                    reg_usr.username=data['name']
                    reg_usr.save()

                    umaps = UserMapping.objects.filter(registration=reg_usr)
                    if umaps:
                        umaps[0].globaluser = data['name']
                        umaps[0].save()

                result = super(UpdateUserForm, self).handle(request, data)
                if not result or isinstance(result, http.HttpResponse):
                    raise Exception()

        except:
            # Workaround for calling a roll-back
            LOG.debug("Called roll-back for update user " + user_id, exc_info=True)

        return result


class ReactivateForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ReactivateForm, self).__init__(request, *args, **kwargs)

        self.fields['userid'] = forms.CharField(
            label=_("User ID"),
            widget=HiddenInput
        )

        self.fields['projects'] = forms.MultipleChoiceField(
            label=_('Available projects'),
            required=True,
            widget=forms.SelectMultiple(attrs={'class': 'switched'})
        )

        avail_prjs = list()
        for prj_entry in Project.objects.exclude(status = PRJ_PRIVATE):
            avail_prjs.append((prj_entry.projectname, prj_entry.projectname))
        self.fields['projects'].choices = avail_prjs

        self.fields['action'] = forms.ChoiceField(
            label=_('Re-activation mode'),
            choices = [
                ('forward', _('Forward to project admin')),
                ('forced', _('Forced reactivation'))
            ],
            widget=forms.Select(attrs={
                'class': 'switchable',
                'data-slug': 'actsource'
            })
        )

        self.fields['expdate'] = forms.DateTimeField(
            label=_("Expiration date"),
            widget=SelectDateWidget({
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-forced': _("Expiration date")
            }, get_year_list())
        )

        self.fields['notes'] = forms.CharField(
            label=_('Notes'),
            required=False,
            widget=forms.widgets.Textarea(attrs = {
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-forward': _("Notes")
            })
        )

    def clean(self):
        if not self.request.user.is_superuser:
            raise ValidationError(_("Operation not authorized"))

        return super(ReactivateForm, self).clean()

    def handle(self, request, data):

        if data['action'] == 'forced':
            result = self.handle_forced(request, data)
        else:
            result = self.handle_forward(request, data)

        #
        # Re-enable user on keystone
        #
        k_user = keystone_api.user_get(request, data['userid'])
        if not k_user.enabled:
            keystone_api.user_update(request, data['userid'], enabled=True)

        return result

    def handle_forced(self, request, data):
        try:

            with transaction.atomic():
                reg_user = Registration.objects.filter(userid=data['userid'])[0]
                prj_list = Project.objects.filter(projectname__in=data['projects'])

                reg_user.expdate = data['expdate']
                reg_user.save()

                #
                # Enable reminder for cloud admin if present
                #
                RegRequest.objects.filter(
                    registration = reg_user,
                    flowstatus = RSTATUS_REMINDER
                ).update(flowstatus = RSTATUS_REMINDACK)

                #
                # Manage user on gate
                #
                RegRequest.objects.filter(
                    registration = reg_user,
                    flowstatus = RSTATUS_DISABLING
                ).delete()

                RegRequest.objects.filter(
                    registration = reg_user,
                    flowstatus = RSTATUS_DISABLED
                ).update(flowstatus = RSTATUS_REENABLING)

        except:
            LOG.error("Generic failure", exc_info=True)
            return False

        for prj_item in prj_list:

            try:
                with transaction.atomic():
                    Expiration.objects.create_expiration(
                        registration = reg_user,
                        project = prj_item,
                        expdate = data['expdate']
                    )

                    keystone_api.add_tenant_user_role(request, prj_item.projectid,
                                                      data['userid'], DEFAULT_ROLEID)

                #
                # send notification to project managers and users
                #
                tmpres = EMail.objects.filter(registration__userid=data['userid'])
                user_email = tmpres[0].email if tmpres else None

                m_userids = [
                    x.userid for x in PrjRole.objects.filter(
                        registration__userid__isnull = False,
                        project__projectid = prj_item.projectid)
                ]
                tmpres = EMail.objects.filter(registration__userid__in = m_userids)
                m_emails = [ x.email for x in tmpres ]

                noti_params = {
                    'username' : reg_user.username,
                    'project' : prj_item.projectname
                }

                notifyProject(request=self.request, rcpt=m_emails,
                              action=SUBSCR_FORCED_OK_TYPE, context=noti_params,
                              dst_project_id=prj_item.projectid)
                notifyUser(request=self.request, rcpt=user_email,
                           action=SUBSCR_OK_TYPE, context=noti_params,
                           dst_project_id=prj_item.projectid,
                           dst_user_id=reg_user.userid)

            except:
                LOG.error("Generic failure", exc_info=True)
        return True


    def handle_forward(self, request, data):
        try:
            with transaction.atomic():

                reg_user = Registration.objects.filter(userid=data['userid'])[0]
                prj_list = Project.objects.filter(projectname__in=data['projects'])

                for prj_item in prj_list:
                    reqArgs = {
                        'registration' : reg_user,
                        'project' : prj_item,
                        'flowstatus' : PSTATUS_PENDING,
                        'notes' : data['notes']
                    }                
                    reqPrj = PrjRequest(**reqArgs)
                    reqPrj.save()

                    try:
                        #
                        # send notification to project managers and users
                        #
                        admin_emails = list()
                        for prj_role in PrjRole.objects.filter(project=prj_item):
                            for email_obj in EMail.objects.filter(registration=prj_role.registration):
                                admin_emails.append(email_obj.email)

                        noti_params = {
                            'username' : reg_user.username,
                            'project' : prj_item.projectname
                        }
                        notifyProject(request=request, rcpt=admin_emails, action=MEMBER_REQUEST, 
                                      context=noti_params)
                    except:
                        LOG.error("Generic failure", exc_info=True)

        except:
            LOG.error("Generic failure", exc_info=True)
            return False

        return True

