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
import json
import threading
from types import ListType, TupleType
from ConfigParser import ConfigParser

from django.conf import settings
from django.core.mail import send_mail, mail_managers
from django.template import Template as DjangoTemplate
from django.template import Context as DjangoContext
from django.utils.translation import ugettext as _
from horizon import messages as MESSAGES

from .models import Log


LOG = logging.getLogger(__name__)

TEMPLATE_TABLE = dict()
TEMPLATE_LOCK = threading.Lock()
TEMPLATE_REGEX = re.compile("notifications_(\w\w).txt")

# List of available notification templates
CHANGED_MEMBER_ROLE = 'changed_member_priv'
FIRST_REG_OK_TYPE = 'first_registration_ok'
FIRST_REG_NO_TYPE = 'first_registration_rejected'
MEMBER_REMOVED = 'member_removed'
MEMBER_REMOVED_ADM = 'member_removed_for_admin'
MEMBER_REQUEST = 'member_request'
PRJ_CREATE_TYPE = 'project_created'
NEWPRJ_REQ_TYPE = 'project_creation_request'
PRJ_REJ_TYPE = 'project_rejected'
REGISTR_AVAIL_TYPE = 'registration_available'
SUBSCR_FORCED_OK_TYPE = 'subscription_forced_approved'
SUBSCR_FORCED_NO_TYPE = 'subscription_forced_rejected'
SUBSCR_ONGOING = 'subscription_ongoing'
SUBSCR_OK_TYPE = 'subscription_processed'
SUBSCR_NO_TYPE = 'subscription_rejected'
SUBSCR_REMINDER = 'subscription_reminder'
SUBSCR_WAIT_TYPE = 'subscription_waiting_approval'
USER_EXP_TYPE = 'user_expiring'
USER_RENEWED_TYPE = 'user_renewed'
USER_PURGED_TYPE = 'user_purged'


DEF_MSG_CACHE_DIR = '/var/cache/openstack-auth-shib/msg'


# DO NOT CHANGE the LOG_TYPE_* constants
LOG_TYPE_EMAIL = '__EMAIL__'


MANAGERS_RCPT = '__MANAGERS__'


class NotificationTemplate():

    def __init__(self, sbj, body):
        self.subject = DjangoTemplate(sbj)
        self.body = DjangoTemplate(body)
    
    def render(self, ctx_dict):
        ctx = DjangoContext(ctx_dict)
        return (self.subject.render(ctx), self.body.render(ctx))


def _log_notify(rcpt, action, context, locale='en', request=None,
                user_id=None, project_id=None,
                user_name=None, project_name=None,
                dst_user_id=None, dst_project_id=None):
    def _try_get_from_request_user(request, field):
        value = None
        try:
            user = request.user
            value = getattr(user, field)
        except Exception as ex:
            LOG.warning("Exception on accessing request.user.{field}: {ex}".
                        format(field=field, ex=ex))
        return value

    if user_id is None:
        user_id = _try_get_from_request_user(request, 'id')

    if project_id is None:
        project_id = _try_get_from_request_user(request, 'project_id')

    if user_name is None:
        user_name = _try_get_from_request_user(request, 'username')

    if project_name is None:
        project_name = _try_get_from_request_user(request, 'project_name')

    LOG.debug("notify user_id={user_id}, project_id={project_id}, "
              "user_name={user_name}, project_name={project_name}, "
              "dst_user_id={dst_user_id}, dst_project_id={dst_project_id}, "
              "rcpt={rcpt}, action={action}, context={context}"
              .format(user_id=user_id, project_id=project_id,
                      user_name=user_name, project_name=project_name,
                      dst_user_id=dst_user_id, dst_project_id=dst_project_id,
                      rcpt=rcpt, action=action, context=context))

    subject, body = notification_render(action, context, locale)
    to = rcpt
    if not type(to) is ListType:
        to = [to, ]
    to = ', '.join(map(str, to))

    msg = "To: {to}\nSubject: {subject}\n\n{body}".format(to=to, subject=subject, body=body)

    Log.objects.log_action(
        log_type=LOG_TYPE_EMAIL,
        action=action,
        message=msg,
        project_id=project_id,
        user_id=user_id,
        project_name=project_name,
        user_name=user_name,
        dst_project_id=dst_project_id,
        dst_user_id=dst_user_id,
    )

    if rcpt == MANAGERS_RCPT:
        notifyManagers(subject, body)
    else:
        notify(rcpt, subject, body)

    MESSAGES.info(request, "Notification sent.")


def warn_if_missing(arg_name):
    def wrapper(func):
        def wrapped(*args, **kwargs):
            if arg_name not in kwargs:
                LOG.warn("{func_name}: `{arg_name}` not given. The log will not be visible by the corresponding entity"
                         .format(func_name=func.__name__, arg_name=arg_name))
            return func(*args, **kwargs)
        return wrapped
    return wrapper


@warn_if_missing('dst_user_id')
def notifyUser(rcpt, action, context, locale='en', *args, **kwargs):
    _log_notify(rcpt, action, context, locale, **kwargs)


@warn_if_missing('dst_project_id')
def notifyProject(rcpt, action, context, locale='en', *args, **kwargs):
    # ensure dst_user_id is not set
    kwargs.pop('dst_user_id', None)

    _log_notify(rcpt, action, context, locale, **kwargs)


def notifyAdmin(action, context, locale='en', *args, **kwargs):
    # ensure nor dst_user_id nor dst_project_id are set
    kwargs.pop('dst_project_id', None)
    kwargs.pop('dst_user_id', None)

    _log_notify(MANAGERS_RCPT, action, context, locale, **kwargs)


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
    if not recpt:
        LOG.error('Missing recipients')
        return
    if type(recpt) is ListType:
        recipients = recpt
    else:
        recipients = [ str(recpt) ]
    
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

def bookNotification(code, userid, username, projectid, projectname):

    cache_dir = getattr(settings, 'MSG_CACHE_DIR', DEF_MSG_CACHE_DIR)
    f_name = os.path.join(cache_dir, "%s.%s" % (projectid, userid))
    t_name = "%s.tmp" % f_name

    try:        
        with open(t_name, 'w') as n_file:
            j_dict = { 
                'code' : code,
                'user' : username,
                'userid' : userid,
                'project' : projectname,
                'projectid' : projectid
            }
            n_file.write(json.dumps(j_dict) + '\n')
        
        os.rename(t_name, f_name)

    except:
        LOG.error("Cannot book notification", exc_info=True)       

