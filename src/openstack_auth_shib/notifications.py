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
from types import ListType

from django.conf import settings
from django.core.mail import send_mail, mail_managers
from django.utils.translation import ugettext as _

LOG = logging.getLogger(__name__)

FOOTER_DISCLAIMER = _("Please, don't reply to this message")

class NotificationMessage():

    def __init__(self, **kwargs):
        self.subject = _(kwargs['subject'])
        if 'body' in kwargs:
            self.body = "%s\n%s" %(_(kwargs['body']), FOOTER_DISCLAIMER)

class RegistrAvailable(NotificationMessage):

    def __init__(self, **kwargs):
        self.subject = _("New request for registration available")
        self.body = _('A new request for registration is available') + '\n'
        
        if 'username' in kwargs:
            self.body += _("The user name is %s") % kwargs['username'] + '\n'

        self.body += FOOTER_DISCLAIMER + '\n'


def notify(recpt, msg_obj):
    
    if not getattr(settings, 'EMAIL_HOST', None):
        LOG.debug('Notification disable')
        return
    
    sender = settings.SERVER_EMAIL
    if type(recpt) is ListType:
        recipients = recpt
    else:
        recipients = [ str(recpt) ]
    
    if len(recipients) == 0:
        LOG.error('Missing recipients')
        return
        
    try:
        send_mail(msg_obj.subject, msg_obj.body, sender, recipients)
        LOG.debug("Sending %s - %s - to %s" % (msg_obj.subject, msg_obj.body, str(recipients)))
    except:
        LOG.error("Cannot send notification", exc_info=True)


def notifyManagers(msg_obj):

    if not getattr(settings, 'EMAIL_HOST', None):
        LOG.debug('Notification disable')
        return

    try:
        mail_managers(msg_obj.subject, msg_obj.body)
        LOG.debug("Sending %s - %s - to managers" % (msg_obj.subject, msg_obj.body))
    except:
        LOG.error("Cannot send notification", exc_info=True)




