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

#
# Workaround for activating the selector
#
DEFAULT_ROLE_ID = "00000"
DEFAULT_ROLE_NAME = "dummy role"

from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PrjRequest

class ApproveAccountAction(workflows.MembershipAction):

    def __init__(self, request, *args, **kwargs):
        super(ApproveAccountAction, self).__init__(request, *args, **kwargs)
        
        err_msg = _('Unable to retrieve account list. Please try again later.')
        
        try:
            default_role_name = self.get_default_role_field_name()
            self.fields[default_role_name] = forms.CharField(required=False)
            self.fields[default_role_name].initial = DEFAULT_ROLE_ID
            
            account_list = list()
            
            regid = int(self.initial["regid"])
            userReqList = RegRequest.objects.filter(registration__regid__exact=regid)
            
            for reg_req in userReqList:
                if reg_req.externalid:
                    ext_acct, ext_idp = reg_req.externalid.split('@')
                    tmpname = _("%s from %s <%s>") % (ext_acct, ext_idp, reg_req.email)
                    account_list.append((reg_req.externalid, tmpname))
                else:
                    tmpname = _("local user <%s>") % reg_req.email
                    account_list.append(('none', tmpname))
            
            field_name = self.get_member_field_name(DEFAULT_ROLE_ID)
            label = DEFAULT_ROLE_NAME
            self.fields[field_name] = forms.MultipleChoiceField(required=False, label=label)
            self.fields[field_name].choices = account_list
            self.fields[field_name].initial = []
        
        except Exception:
            exceptions.handle(self.request,
                              err_msg,
                              redirect=reverse_lazy('horizon:admin:registration_manager:index'))

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

    def contribute(self, data, context):
        if data:
            try:                

                post = self.workflow.request.POST
                field = self.get_member_field_name(DEFAULT_ROLE_ID)
                context[field] = post.getlist(field)
                
            except Exception:
                exceptions.handle(self.workflow.request, _('Unable to retrieve role list.'))

        return context



class ApprovePrjMemberAction(workflows.MembershipAction):

    def __init__(self, request, *args, **kwargs):
        super(ApprovePrjMemberAction, self).__init__(request, *args, **kwargs)
        
        err_msg = _('Unable to retrieve project list. Please try again later.')
        
        try:

            default_role_name = self.get_default_role_field_name()
            self.fields[default_role_name] = forms.CharField(required=False)
            self.fields[default_role_name].initial = DEFAULT_ROLE_ID
            
            prj_list = list()
            
            regid = int(self.initial["regid"])
            prjReqList = PrjRequest.objects.filter(registration__regid__exact=regid)
            for prj_req in prjReqList:
                prjname = prj_req.project.projectname
                prj_list.append((prjname, prjname))
            
            field_name = self.get_member_field_name(DEFAULT_ROLE_ID)
            label = DEFAULT_ROLE_NAME
            self.fields[field_name] = forms.MultipleChoiceField(required=False, label=label)
            self.fields[field_name].choices = prj_list
            self.fields[field_name].initial = []
            
        except Exception:
            exceptions.handle(self.request,
                              err_msg,
                              redirect=reverse_lazy('horizon:admin:registration_manager:index'))

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

    def contribute(self, data, context):
        if data:
            try:

                post = self.workflow.request.POST
                field = self.get_member_field_name(DEFAULT_ROLE_ID)
                context[field] = post.getlist(field)

            except Exception:
                exceptions.handle(self.workflow.request, _('Unable to retrieve role list.'))
        
        return context




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
        try:
            
            acct_step = self.get_step('approve_account')
            field_name = acct_step.get_member_field_name(DEFAULT_ROLE_ID)
            approved_accts = data[field_name]
            
            LOG.debug("Approved accounts: %s" % str(approved_accts))
        
            prjmem_step = self.get_step('approve_prjmember')
            field_name = prjmem_step.get_member_field_name(DEFAULT_ROLE_ID)
            approved_prjs = data[field_name]

            LOG.debug("Approved projects: %s" % str(approved_prjs))
        
        except:
            LOG.error("Failure in handle", exc_info=True)
        
        return True





