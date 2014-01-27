import logging

from horizon import forms
from horizon import workflows
from horizon import exceptions

from django.conf import settings 
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.debug import sensitive_variables

from openstack_dashboard import api

LOG = logging.getLogger(__name__)

from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PrjRequest

class ApproveAccountAction(workflows.MembershipAction):

    def __init__(self, request, *args, **kwargs):
        super(ApproveAccountAction, self).__init__(request, *args, **kwargs)
        
        err_msg = _('Unable to retrieve account list. Please try again later.')
        
        try:
            default_role = api.keystone.get_default_role(self.request)
            if default_role is None:
                default = getattr(settings, "OPENSTACK_KEYSTONE_DEFAULT_ROLE", None)
                msg = _('Could not find default role "%s" in Keystone') % default
                raise exceptions.NotFound(msg)
        except Exception:
            exceptions.handle(self.request,
                              err_msg,
                              redirect=reverse_lazy('horizon:admin:registration_manager:index'))

        default_role_name = self.get_default_role_field_name()
        self.fields[default_role_name] = forms.CharField(required=False)
        self.fields[default_role_name].initial = default_role.id
        
        role_list = list()
        account_list = list()
        
        try:
        
            regid = self.initial["regid"]
            userReqList = RegRequest.objects.filter(registration__regid__exact=int(regid))
            for reg_req in userReqList:
                if reg_req.externalid:
                    ext_acct, ext_idp = reg_req.externalid.split('@')
                    tmpname = _("%s from %s <%s>") % (ext_acct, ext_idp, reg_req.email)
                    account_list.append((reg_req.externalid, tmpname))
                else:
                    tmpname = _("local user <%s>") % reg_req.email
                    account_list.append(('none', tmpname))
        
            role_list = api.keystone.role_list(request)

        except Exception:
            exceptions.handle(request,
                              err_msg,
                              redirect=reverse_lazy('horizon:admin:registration_manager:index'))
        
        for role in role_list:
            field_name = self.get_member_field_name(role.id)
            label = role.name
            self.fields[field_name] = forms.MultipleChoiceField(required=False,
                                                                label=label)
            self.fields[field_name].choices = account_list
            self.fields[field_name].initial = []

    class Meta:
        slug = "approve_account"
        name = _("Accounts")
        
class ApproveAccount(workflows.UpdateMembersStep):
    action_class = ApproveAccountAction
    depends_on = ("regid",)
    available_list_title = _("Pending accounts")
    members_list_title = _("Approved account")
    no_available_text = _("No accounts found.")
    no_members_text = _("No accounts.")
    show_roles = False



class ApprovePrjMemberAction(workflows.MembershipAction):

    def __init__(self, request, *args, **kwargs):
        super(ApprovePrjMemberAction, self).__init__(request, *args, **kwargs)
        
        err_msg = _('Unable to retrieve project list. Please try again later.')
        
        try:
            default_role = api.keystone.get_default_role(self.request)
            if default_role is None:
                default = getattr(settings, "OPENSTACK_KEYSTONE_DEFAULT_ROLE", None)
                msg = _('Could not find default role "%s" in Keystone') % default
                raise exceptions.NotFound(msg)
        except Exception:
            exceptions.handle(self.request,
                              err_msg,
                              redirect=reverse_lazy('horizon:admin:registration_manager:index'))

        default_role_name = self.get_default_role_field_name()
        self.fields[default_role_name] = forms.CharField(required=False)
        self.fields[default_role_name].initial = default_role.id

        role_list = list()
        prj_list = list()
        
        try:
        
            regid = self.initial["regid"]
            prjReqList = PrjRequest.objects.filter(registration__regid__exact=int(regid))
            for prj_req in prjReqList:
                prjname = prj_req.project.projectname
                prj_list.append((prjname, prjname))
        
            role_list = api.keystone.role_list(request)

        except Exception:
            exceptions.handle(request,
                              err_msg,
                              redirect=reverse_lazy('horizon:admin:registration_manager:index'))

        for role in role_list:
            field_name = self.get_member_field_name(role.id)
            label = role.name
            self.fields[field_name] = forms.MultipleChoiceField(required=False,
                                                                label=label)
            self.fields[field_name].choices = prj_list
            self.fields[field_name].initial = []

    class Meta:
        slug = "approve_prjmember"
        name = _("Project member")



class ApprovePrjMember(workflows.UpdateMembersStep):
    action_class = ApprovePrjMemberAction
    available_list_title = _("Pending projects")
    members_list_title = _("Approved projects")
    no_available_text = _("No projects found.")
    no_members_text = _("No projects.")
    show_roles = False





class ApproveRegWorkflow(workflows.Workflow):
    slug = "approve_registration"
    name = _("Approve registration")
    finalize_button_name = _("Save")
    success_message = _('Approved registration "%s".')
    failure_message = _('Unable to approve registration "%s".')
    success_url = reverse_lazy('horizon:admin:registration_manager:index')
    
    default_steps = (ApproveAccount,
                     ApprovePrjMember)

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):

        super(ApproveRegWorkflow, self).__init__(request=request,
                                                 context_seed=context_seed,
                                                 entry_point=entry_point,
                                                 *args, **kwargs)

    @sensitive_variables('data')
    def handle(self, request, data):
        LOG.debug("Handling workflow")
        return True





