from django.utils.translation import ugettext as _

from openstack_auth_shib.notifications import notifyManagers, NotificationMessage
from openstack_auth_shib.notifications import FOOTER_DISCLAIMER

class SubscrChecked(NotificationMessage):

    def __init__(self, **kwargs):
        self.subject = _("Subscription has been checked")
        self.body = _('A subscription has been checked by project manager') + '\n'
        
        if 'username' in kwargs:
            self.body += _("The user name is %s") % kwargs['username'] + '\n'
        if 'project' in kwargs:
            self.body += _("The project is %s") % kwargs['project'] + '\n'
        
        self.body += FOOTER_DISCLAIMER + '\n'
    
