import logging
import base64
from Crypto import __version__ as crypto_version
if crypto_version.startswith('2.0'):
    from Crypto.Util import randpool
else:
    from Crypto import Random

from horizon import forms
from horizon import workflows
from horizon import exceptions

from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.debug import sensitive_variables

from openstack_dashboard.api import keystone as keystone_api

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import RegRequest
from openstack_auth_shib.models import PrjRequest
from openstack_auth_shib.models import UserMapping

LOG = logging.getLogger(__name__)

#
# Workaround for activating the selector
#
DEFAULT_ROLE_ID = "00000"
DEFAULT_ROLE_NAME = "dummy role"




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
            qargs = {
                'registration__regid__exact' : regid,
            }
            userReqList = RegRequest.objects.filter(**qargs).exclude(externalid=None)
            
            for reg_req in userReqList:
                ext_acct, ext_idp = reg_req.externalid.split('@')
                tmpname = _("%s from %s <%s>") % (ext_acct, ext_idp, reg_req.email)
                account_list.append((reg_req.externalid, tmpname))
            
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






class ApproveUserAction(workflows.Action):

    username = forms.CharField(label=_("User name"))
    role_id = forms.ChoiceField(label=_("Role"))
    
    def __init__(self, request, *args, **kwargs):
        super(ApproveUserAction, self).__init__(request, *args, **kwargs)
        
        role_list = keystone_api.role_list(request)
        role_choices = [(role.id, role.name) for role in role_list]
        self.fields['role_id'].choices = role_choices
        
    class Meta:
        slug = "approve_user"
        name = _("User data")

class ApproveUser(workflows.Step):
    action_class = ApproveUserAction
    contributes = ("role_id",)
    depends_on = ("regid", "username")






class ApproveRegWorkflow(workflows.Workflow):
    slug = "approve_registration"
    name = _("Approve registration")
    finalize_button_name = _("Save")
    success_message = _('Approved registration "%s".')
    failure_message = _('Unable to approve registration "%s".')
    success_url = reverse_lazy('horizon:admin:registration_manager:index')

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):

        self.default_steps = (ApproveAccount, ApprovePrjMember)

        if context_seed and 'userid' in context_seed:
            if context_seed['userid'] is None:
                self.default_steps = (ApproveUser, ApproveAccount, ApprovePrjMember)

        
        super(ApproveRegWorkflow, self).__init__(request=request,
                                                 context_seed=context_seed,
                                                 entry_point=entry_point,
                                                 *args, **kwargs)

    def _generate_pwd(self):
        if crypto_version.startswith('2.0'):
            prng = randpool.RandomPool()
        else:
            prng = Random.new()
        iv = prng.read(16)
        return base64.b64encode(iv)
    
    @sensitive_variables('data')
    def handle(self, request, data):
        try:
            
            with transaction.commit_on_success():
            
                regid = int(data["regid"])
                registration = None
                email = None
                password = None

                #
                # Registration of the external identities
                #
                acct_step = self.get_step('approve_account')
                field_name = acct_step.get_member_field_name(DEFAULT_ROLE_ID)
                approved_accts = data[field_name]
            
                userReqList = RegRequest.objects.filter(registration__regid__exact=regid)
            
                for tmpReq in userReqList:
                    if not registration:
                        registration = tmpReq.registration
                    
                    if tmpReq.password and not password:
                        password = tmpReq.password

                    if tmpReq.externalid and tmpReq.externalid in approved_accts:
                        mapping = UserMapping(globaluser=tmpReq.externalid,
                                              registration=tmpReq.registration)
                        mapping.save()
                    
                        if not email:
                            email = tmpReq.email
                    
                    if not tmpReq.externalid and not email:
                        email = tmpReq.email

                    tmpReq.delete()
                   
                #
                # First registration of the local user
                #
                prjmem_step = self.get_step('approve_prjmember')
                field_name = prjmem_step.get_member_field_name(DEFAULT_ROLE_ID)
                approved_prjs = data[field_name]

                if not registration.userid:
                
                    if len(approved_prjs) == 0:
                        raise Exception("No tenants for first registration")
                    
                    if not email:
                        raise Exception("No email for first registration")
                    
                    if not password:
                        password = self._generate_pwd()
                        
                    first_prj = approved_prjs.pop()
                    kuser = keystone_api.user_create(request, name=data['username'],
                                                     password=password, email=email,
                                                     project=first_prj,
                                                     enabled=True, domain='Default')
                    
                    keystone_api.add_tenant_user_role(request,first_prj,
                                                               kuser.id, data['role_id'])

                    registration.userid = kuser.id
                    registration.username = data['username']
                    registration.save()
                    
                #
                # Registration of the tenants
                #
                prjReqList = PrjRequest.objects.filter(registration__regid__exact=regid)
                
                for tmpPrj in prjReqList:
                    if tmpPrj in approved_prjs:
                        pass
                        
                    tmpPrj.delete()
                
        except:
            LOG.error("Failure in handle", exc_info=True)
            exceptions.handle(request, _('Unable to approve request.'))
        
        return True





