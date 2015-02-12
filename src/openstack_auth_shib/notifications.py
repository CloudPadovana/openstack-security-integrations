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
import os, os.path
import re
import threading
from types import ListType, TupleType
from ConfigParser import ConfigParser

from django.conf import settings
from django.core.mail import send_mail, mail_managers
from django.template import Template as DjangoTemplate
from django.template import Context as DjangoContext
from django.utils.translation import ugettext as _

LOG = logging.getLogger(__name__)

TEMPLATE_TABLE = dict()
TEMPLATE_LOCK = threading.Lock()
TEMPLATE_REGEX = re.compile("notifications_(\w\w).txt")

# List of available notification templates
REGISTR_AVAIL_TYPE = 'registration_available'
SUBSCR_REQ_TYPE = 'subscription_request'
SUBSCR_CHKD_TYPE = 'subscription_checked'
SUBSCR_WAIT_TYPE = 'subscription_waiting_approval'
FIRST_REG_OK_TYPE = 'first_registration_ok'
FIRST_REG_NO_TYPE = 'first_registration_rejected'
SUBSCR_OK_TYPE = 'subscription_processed'
SUBSCR_NO_TYPE = 'subscription_rejected'
SUBSCR_FORCED_OK_TYPE = 'subscription_forced_approved'
SUBSCR_FORCED_NO_TYPE = 'subscription_forced_rejected'


class NotificationTemplate():

    def __init__(self, sbj, body):
        self.subject = DjangoTemplate(sbj)
        self.body = DjangoTemplate(body)
    
    def render(self, ctx_dict):
        ctx = DjangoContext(ctx_dict)
        return (self.subject.render(ctx), self.body.render(ctx))

def notification_render(msg_type, ctx_dict, locale='en'):

    load_templates()
    
    notify_tpl = TEMPLATE_TABLE[locale].get(msg_type, None)
    if notify_tpl:
        return notify_tpl.render(ctx_dict)
    return (None, None)

def load_templates():

    TEMPLATE_LOCK.acquire()
    
    if len(TEMPLATE_TABLE):
        TEMPLATE_LOCK.release()
        return

    LOG.debug('Filling in the template table')
    tpl_dir = getattr(settings, 'NOTIFICATION_TEMPLATE_DIR', '/usr/share/openstack-auth-shib/templates')
    
    try:
        for tpl_item in os.listdir(tpl_dir):
            res_match = TEMPLATE_REGEX.search(tpl_item)
            if not res_match:
                continue
            
            locale = res_match.group(1).lower()
            TEMPLATE_TABLE[locale] = dict()
        
            tpl_filename = os.path.join(tpl_dir, tpl_item)
            parser = ConfigParser()
            parser.readfp(open(tpl_filename))
        
            for sect in parser.sections():
            
                sbj = parser.get(sect, 'subject') if parser.has_option(sect, 'subject') else "No subject"
                body = parser.get(sect, 'body') if parser.has_option(sect, 'body') else "No body"
                TEMPLATE_TABLE[locale][sect] = NotificationTemplate(sbj, body)
        
    except:
        #
        # TODO need cleanup??
        #
        LOG.error("Cannot load template table", exc_info=True)

    TEMPLATE_LOCK.release()

def notify(recpt, subject, body):
    
    sender = settings.SERVER_EMAIL
    if type(recpt) is ListType:
        recipients = recpt
    else:
        recipients = [ str(recpt) ]
    
    if len(recipients) == 0:
        LOG.error('Missing recipients')
        return
        
    try:
        send_mail(subject, body, sender, recipients)
        LOG.debug("Sending %s - %s - to %s" % (subject, body, str(recipients)))
    except:
        LOG.error("Cannot send notification", exc_info=True)


def notifyManagers(subject, body):

    try:
        mail_managers(subject, body)
        LOG.debug("Sending %s - %s - to managers" % (subject, body))
    except:
        LOG.error("Cannot send notification", exc_info=True)




