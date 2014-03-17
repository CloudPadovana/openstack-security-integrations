import logging
from types import StringType

from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import ugettext as _

LOG = logging.getLogger(__name__)

FOOTER_DISCLAIMER = _("Please, don't reply to this message")

class NotificationMessage():

    def __init__(self, **kwargs):
        self.subject = _(kwargs['subject'])
        if 'body' in kwargs:
            self.body = "%s\n%s" %(_(kwargs['body']), FOOTER_DISCLAIMER)

def notify(recpt, msg_obj):
    
    if not getattr(settings, 'EMAIL_HOST', None):
        LOG.debug('Notification disable')
        return
    
    sender = getattr(settings, 'EMAIL_SENDER', 'cloud@lists.pd.infn.it')
    if type(recpt) is StringType:
        recipients = [ recpt ]
    else:
        recipients = recpt
    
    if len(recipients) == 0:
        LOG.error('Missing recipients')
        return
        
    try:
        #send_mail(msg_obj.subject, msg_obj.body, sender, recipients)
        LOG.debug("Sending %s - %s - to %s" % (msg_obj.subject, msg_obj.body, str(recipients)))
    except:
        LOG.error("Cannot send notification", exc_info=True)


