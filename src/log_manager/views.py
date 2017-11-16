#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  Copyright (c) 2017 INFN - "Istituto Nazionale di Fisica Nucleare" - Italy
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

from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from horizon import exceptions
from horizon import tables
from horizon import forms
from horizon import messages
from horizon import views
from horizon.utils import memoized
from openstack_dashboard import api

from openstack_auth_shib.models import Log
from openstack_auth_shib.notifications import LOG_TYPE_EMAIL
from .tables import MainTable


LOG = logging.getLogger(__name__)


# Date range handling is based on openstack_dashboard/usage/base.py
class DateRange(object):
    def __init__(self, request):
        self.request = request

    @property
    def today(self):
        return timezone.now()

    @property
    def first_day(self):
        days_range = getattr(settings, 'LOG_MANAGER_DAYS_RANGE', 1)
        if days_range:
            return self.today.date() - datetime.timedelta(days=days_range)
        else:
            return datetime.date(self.today.year, self.today.month, 1)

    @staticmethod
    def get_start(year, month, day):
        start = datetime.datetime(year, month, day, 0, 0, 0)
        return timezone.make_aware(start, timezone.utc)

    @staticmethod
    def get_end(year, month, day):
        end = datetime.datetime(year, month, day, 23, 59, 59)
        return timezone.make_aware(end, timezone.utc)

    def init_form(self):
        self.start = self.first_day
        self.end = self.today.date()

        return self.start, self.end

    def get_date_range(self):
        if not hasattr(self, "start") or not hasattr(self, "end"):
            args_start = (self.first_day.year, self.first_day.month,
                          self.first_day.day)
            args_end = (self.today.year, self.today.month, self.today.day)
            form = self.get_form()
            if form.is_valid():
                start = form.cleaned_data['start']
                end = form.cleaned_data['end']
                args_start = (start.year,
                              start.month,
                              start.day)
                args_end = (end.year,
                            end.month,
                            end.day)
            elif form.is_bound:
                messages.error(self.request,
                               _("Invalid date format: "
                                 "Using today as default."))
            self.start = self.get_start(*args_start)
            self.end = self.get_end(*args_end)
        return self.start, self.end

    def get_form(self):
        if not hasattr(self, 'form'):
            req = self.request
            start = req.GET.get('start', req.session.get('logs_start'))
            end = req.GET.get('end', req.session.get('logs_end'))
            if start and end:
                # bound form
                self.form = forms.DateForm({'start': start, 'end': end})
            else:
                # non-bound form
                init = self.init_form()
                start = init[0].isoformat()
                end = init[1].isoformat()
                self.form = forms.DateForm(initial={'start': start,
                                                    'end': end})
            req.session['logs_start'] = start
            req.session['logs_end'] = end
        return self.form


def _get_project_name(request, project_id):
    project_name = None
    if project_id:
        try:
            project = api.keystone.tenant_get(request, project_id)
            project_name = project.name
        except Exception as e:
            msg = ('Failed to get project %(project_id)s: %(reason)s' %
                   {'project_id': project_id, 'reason': e})
            LOG.error(msg)
    return project_name


def _get_user_name(request, user_id):
    user_name = None
    if user_id:
        try:
            user = api.keystone.user_get(request, user_id)
            user_name = user.name
        except Exception as e:
            msg = ('Failed to get user %(user_id)s: %(reason)s' %
                   {'user_id': user_id, 'reason': e})
            LOG.error(msg)
    return user_name


class MainView(tables.DataTableView):
    table_class = MainTable
    template_name = 'idmanager/log_manager/log_manager.html'
    page_title = _("Logs")

    def get_data(self):
        logs = []

        self.date_range = DateRange(self.request)
        start, end = self.date_range.get_date_range()

        filters = self.get_filters()
        filters['timestamp__gte'] = start
        filters['timestamp__lte'] = end

        values = Log.objects.filter(**filters)
        for log in values:
            if not log.user_name:
                log.user_name = self.get_user_name(getattr(log, "user_id"))
            if not log.project_name:
                log.project_name = self.get_project_name(getattr(log, "project_id"))

            log.dst_user_name = self.get_user_name(getattr(log, "dst_user_id"))
            log.dst_project_name = self.get_project_name(getattr(log, "dst_project_id"))

            logs.append(log)

        return logs

    def get_context_data(self, **kwargs):
        context = super(MainView, self).get_context_data(**kwargs)
        context['form'] = self.date_range.form

        return context

    @memoized.memoized_method
    def get_project_name(self, project_id):
        return _get_project_name(self.request, project_id)

    @memoized.memoized_method
    def get_user_name(self, user_id):
        return _get_user_name(self.request, user_id)


class DetailView(views.HorizonTemplateView):
    template_name = 'idmanager/log_manager/detail.html'
    page_title = _("Log detail")

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        log = self.get_data()

        context["timestamp"] = getattr(log, "timestamp")
        context["message"] = self.get_message(log)
        context["action"] = getattr(log, "action")

        if getattr(log, "log_type") == LOG_TYPE_EMAIL:
            context["email"] = self.get_email(log)

        context["user_id"] = getattr(log, "user_id", _("None"))
        context["project_id"] = getattr(log, "project_id", _("None"))
        context["user_name"] = getattr(log, "user_name", _("None"))
        context["project_name"] = getattr(log, "project_name", _("None"))

        context["dst_user_id"] = getattr(log, "dst_user_id", _("None"))
        context["dst_project_id"] = getattr(log, "dst_project_id", _("None"))
        context["dst_user_name"] = self.get_user_name(getattr(log, "dst_user_id"))
        context["dst_project_name"] = self.get_project_name(getattr(log, "dst_project_id"))

        context["url"] = self.get_redirect_url()
        return context

    @memoized.memoized_method
    def get_message(self, log):
        return log.message.splitlines()[0]

    @memoized.memoized_method
    def get_email(self, log):
        if getattr(settings, 'LOG_MANAGER_KEEP_NOTIFICATIONS_EMAIL', True):
            return log.message.splitlines()[2:]
        else:
            return None

    @memoized.memoized_method
    def get_project_name(self, project_id):
        return _get_project_name(self.request, project_id)

    @memoized.memoized_method
    def get_user_name(self, user_id):
        return _get_user_name(self.request, user_id)

    @memoized.memoized_method
    def get_data(self):
        try:
            log_id = self.kwargs['log_id']
            log = Log.objects.get(id=log_id)
        except Exception:
            redirect = self.get_redirect_url()
            exceptions.handle(self.request,
                              _('Unable to retrieve log details.'),
                              redirect=redirect)
        return log

    def get_redirect_url(self):
        return reverse('horizon:idmanager:log_manager:index')
