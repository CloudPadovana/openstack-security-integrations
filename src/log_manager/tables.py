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

from django.utils.translation import ugettext_lazy as _
from horizon import tables


LOG = logging.getLogger(__name__)


class LogFilterAction(tables.FilterAction):
    name = "log_filter"

    filter_type = "server"

    filter_choices = (
        ("project_name", _("Project Name ="), True),
        ("project_id", _("Project ID ="), True),
        ("user_name", _("User Name ="), True),
        ("user_id", _("User ID ="), True),
    )


def format_message(row):
    msg = row.message

    ret = msg.splitlines()[0]
    return ret


def format_recipient(row):
    dst_user_id = row.dst_user_id
    dst_project_id = row.dst_project_id
    dst_user_name = row.dst_user_name
    dst_project_name = row.dst_project_name

    ret = []
    if dst_user_id:
        ret.append("USER {user_name}".format(user_name=dst_user_name))
    if dst_project_id:
        ret.append("PROJECT {project_name}".format(project_name=dst_project_name))

    if ret:
        return ", ".join(ret)

    return "Cloud Admin"


def _format_name_id(name, id):
    ret = "Undefined"

    if name:
        ret = name
    elif id:
        ret = "(%s)" % id

    return ret


def format_user(row):
    user_id = row.user_id
    user_name = row.user_name
    return _format_name_id(user_name, user_id)


def format_project(row):
    project_id = row.project_id
    project_name = row.project_name
    return _format_name_id(project_name, project_id)


class MainTable(tables.DataTable):
    timestamp = tables.Column('timestamp', verbose_name=_('Date'))
    action = tables.Column('action', verbose_name=_('Action'))

    user = tables.Column(
        transform=format_user,
        verbose_name=_('User'),
    )

    project = tables.Column(
        transform=format_project,
        verbose_name=_('Project'),
    )

    message = tables.Column(
        transform=format_message,
        verbose_name=_('Message'),
        link="horizon:idmanager:log_manager:detail",
    )

    recipient = tables.Column(
        transform=format_recipient,
        verbose_name=_('Target'),
    )

    class Meta(object):
        name = "logs"
        verbose_name = _("Logs")
        multi_select = False
        table_actions = (LogFilterAction, )
