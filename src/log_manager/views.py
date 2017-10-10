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

from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from horizon import tables
from horizon import forms
from horizon import messages

from openstack_auth_shib.models import Log
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

        logs = Log.objects.filter(**filters)
        return logs

    def get_context_data(self, **kwargs):
        context = super(MainView, self).get_context_data(**kwargs)
        context['form'] = self.date_range.form

        return context
