
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

class PrjManagerMessage(NotificationMessage):

    def __init__(self, **kwargs):
        self.subject = _("Subscription request waiting for approval")
        self.body = _('User %(username)s requires access to project %(projectname)s\n') % kwargs
        self.body += FOOTER_DISCLAIMER + '\n'

class ForcedApprovedMessage(NotificationMessage):

    def __init__(self, **kwargs):
        self.subject = _("Cloud manager forcedly approved subscription")
        self.body = _('Cloud manager forcedly approved the subscription of %(username)s to %(projectname)s\n') % kwargs
        self.body += FOOTER_DISCLAIMER + '\n'

class ForcedRejectedMessage(NotificationMessage):

    def __init__(self, **kwargs):
        self.subject = _("Cloud manager forcedly rejected subscription")
        self.body = _('Cloud manager forcedly rejected the subscription of %(username)s to %(projectname)s\n') % kwargs
        self.body += FOOTER_DISCLAIMER + '\n'

class RequestResultMessage(NotificationMessage):

    def __init__(self, **kwargs):
        self.body = ''
        
        username = kwargs.get('username', None)
        if username:
            self.subject = _("Your registration has been accepted")
            self.body += _("Your account has been registered\n")
            self.body += _("Your login name is %s\n") % username
        else:
            self.subject = _("Your project subscriptions have been evaluated")
        
        prjok_list = kwargs.get('prj_ok', [])
        if prjok_list:
            self.body += _("The following subscriptions have been approved") + '\n'
            for item in prjok_list:
                self.body += item + '\n'
            self.body += '\n'
        
        prjno_list = kwargs.get('prj_no', [])
        if prjno_list:
            self.body += _("The following subscriptions have been rejected") + '\n'
            for item in prjno_list:
                self.body += item + '\n'
            self.body += '\n'
        
        prjnew_list = kwargs.get('prj_new', [])
        if prjnew_list:
            self.body += _("The following projects have been created") + '\n'
            for item in prjnew_list:
                self.body += item + '\n'
            self.body += '\n'

        self.body += FOOTER_DISCLAIMER + '\n'
        
            
