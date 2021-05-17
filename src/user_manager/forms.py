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

from django import http
from django.db import transaction
from django.conf import settings
from django.forms.widgets import HiddenInput
from django.forms.widgets import SelectDateWidget
from django.utils.translation import ugettext as _

from horizon import forms
from horizon import messages

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import Expiration
from openstack_auth_shib.models import EMail
from openstack_auth_shib.models import UserMapping
from openstack_auth_shib.models import PSTATUS_RENEW_ADMIN
from openstack_auth_shib.models import PSTATUS_RENEW_MEMB
from openstack_auth_shib.models import RSTATUS_REMINDER
from openstack_auth_shib.models import RSTATUS_REMINDACK

from openstack_auth_shib.notifications import notifyProject
from openstack_auth_shib.notifications import notifyUser
from openstack_auth_shib.notifications import USER_RENEWED_TYPE
from openstack_auth_shib.notifications import SUBSCR_OK_TYPE
from openstack_auth_shib.notifications import SUBSCR_FORCED_OK_TYPE

from openstack_auth_shib.utils import get_prjman_ids
from openstack_auth_shib.utils import set_last_exp

from openstack_dashboard.api import keystone as keystone_api
from openstack_dashboard.dashboards.identity.users import forms as baseForms

LOG = logging.getLogger(__name__)

def get_year_list():
    curr_year = datetime.now().year
    return list(range(curr_year, curr_year+25))

def get_default_role(request):
    DEFAULT_ROLE = getattr(settings, 'OPENSTACK_KEYSTONE_DEFAULT_ROLE', None)
    for role in keystone_api.role_list(request):
        if role.name == DEFAULT_ROLE:
            return role.id

class RenewExpForm(forms.SelfHandlingForm):


    def __init__(self, request, *args, **kwargs):

        super(RenewExpForm, self).__init__(request, *args, **kwargs)

        self.fields['userid'] = forms.CharField(
            label=_("User ID"), 
            widget=HiddenInput
        )
        
        for item in kwargs['initial']:
            if item.startswith('prj_'):
                self.fields[item] = forms.DateTimeField(
                    label="%s %s" % (_("Project"), item[4:]),
                    widget=SelectDateWidget(None, get_year_list())
                )

    def handle(self, request, data):

        mail_table = dict()
        exp_table = dict()
        for d_item in data:
            if d_item.startswith('prj_'):
                exp_table[d_item[4:]] = data[d_item]

        if not request.user.is_superuser:
            messages.error(_("Operation not authorized"))
            return False

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

                q_args = {
                    'registration__userid' : data['userid'],
                    'project__projectname' : prj_name
                }
                Expiration.objects.filter(**q_args).update(expdate=c_exp)

                q_args['flowstatus__in'] = [ PSTATUS_RENEW_ADMIN, PSTATUS_RENEW_MEMB ]
                PrjRequest.objects.filter(**q_args).delete()
                
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

            set_last_exp(data['userid'])

        return True

class UpdateUserForm(baseForms.UpdateUserForm):

    def __init__(self, request, *args, **kwargs):
        super(UpdateUserForm, self).__init__(request, *args, **kwargs)

    def handle(self, request, data):

        user_id = data['id']

        if not request.user.is_superuser:
            messages.error(_("Operation not authorized"))
            return False

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

        self.fields['expdate'] = forms.DateTimeField(
            label="Expiration date",
            widget=SelectDateWidget(None, get_year_list())
        )

        self.fields['projects'] = forms.MultipleChoiceField(
            label=_('Available projects'),
            required=True,
            widget=forms.SelectMultiple(attrs={'class': 'switched'})
        )

        avail_prjs = list()
        for prj_entry in Project.objects.all():
            avail_prjs.append((prj_entry.projectname, prj_entry.projectname))
        self.fields['projects'].choices = avail_prjs

    def handle(self, request, data):

        if not request.user.is_superuser:
            messages.error(_("Operation not authorized"))
            return False

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

                k_user = keystone_api.user_get(request, data['userid'])
                if not k_user.enabled:
                    keystone_api.user_update(request, data['userid'], enabled=True)

        except:
            LOG.error("Generic failure", exc_info=True)
            return False

        for prj_item in prj_list:

            try:
                with transaction.atomic():
                    Expiration(
                        registration=reg_user,
                        project=prj_item,
                        expdate=data['expdate']
                    ).save()

                    keystone_api.add_tenant_user_role(
                        request, prj_item.projectid,
                        data['userid'], get_default_role(request))

                #
                # send notification to project managers and users
                #
                tmpres = EMail.objects.filter(registration__userid=data['userid'])
                user_email = tmpres[0].email if tmpres else None

                m_userids = get_prjman_ids(request, prj_item.projectid)
                tmpres = EMail.objects.filter(registration__userid__in=m_userids)
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


