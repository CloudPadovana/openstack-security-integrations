
from django.utils.translation import ugettext as _

from openstack_auth_shib.notifications import notify, NotificationMessage
from openstack_auth_shib.notifications import FOOTER_DISCLAIMER

REGISTRATION_NOT_AUTHORIZED = NotificationMessage(
    subject = "Registration not authorized",
    body = "You're not authorized to access the cloud infrastructure"
)

NO_TENANT_AUTHORIZED = NotificationMessage(
    subject = "Tenant subscription not authorized",
    body = "You're not authorized to access the required tenants"
)

class TenantNotifMessage(NotificationMessage):

    def __init__(self, **kwargs):
        self.subject = _("Tenant subscription request")
        self.body = ''
        
        prjok_list = getattr(kwargs, 'prj_ok', [])
        if prjok_list:
            self.body += _("The following subscriptions have been approved") + '\n'
            for item in prjok_list:
                self.body += item + '\n'
            self.body += '\n'
        
        prjno_list = getattr(kwargs, 'prj_no', [])
        if prjno_list:
            self.body += _("The following subscriptions have been rejected") + '\n'
            for item in prjno_list:
                self.body += item + '\n'
            self.body += '\n'
        
        self.body += FOOTER_DISCLAIMER + '\n'
        
            
