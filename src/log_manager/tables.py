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


class MainTable(tables.DataTable):
    timestamp = tables.Column('timestamp', verbose_name=_('Date'))
    action = tables.Column('action', verbose_name=_('Action'))

    user_id = tables.Column('user_id', verbose_name=_('User ID'))
    project_id = tables.Column('project_id', verbose_name=_('Project ID'))

    message = tables.Column('message', verbose_name=_('Message'))
