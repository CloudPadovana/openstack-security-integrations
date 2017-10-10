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


def format_recipient(row):
    dst_user_id = row.dst_user_id
    dst_project_id = row.dst_project_id

    ret = ""
    if dst_project_id and dst_user_id:
        ret = "USER %s of PROJECT %s" % (dst_user_id, dst_project_id)
    elif dst_user_id and not dst_project_id:
        ret = "USER %s" % dst_user_id
    elif dst_project_id and not dst_user_id:
        ret = "PROJECT %s" % dst_project_id
    else:
        ret = "ADMIN"
    return ret


class MainTable(tables.DataTable):
    timestamp = tables.Column('timestamp', verbose_name=_('Date'))
    action = tables.Column('action', verbose_name=_('Action'))

    user = tables.Column(
        transform=lambda row: "{name} ({id})".format(name=row.user_name,
                                                     id=row.user_id),
        verbose_name=_('User'),
    )

    project = tables.Column(
        transform=lambda row: "{name} ({id})".format(name=row.project_name,
                                                     id=row.project_id),
        verbose_name=_('Project'),
    )

    recipient = tables.Column(
        transform=format_recipient,
        verbose_name=_('Recipient'),
    )

    message = tables.Column('message', verbose_name=_('Message'))

    class Meta(object):
        name = "logs"
        verbose_name = _("Logs")
        multi_select = False
        table_actions = (LogFilterAction, )
