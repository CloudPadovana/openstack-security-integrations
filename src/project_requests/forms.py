import logging

from horizon import forms
from horizon import messages

from django.db import transaction
from django.db import IntegrityError
from django.views.decorators.debug import sensitive_variables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PRJ_PUBLIC,PRJ_PRIVATE
from openstack_auth_shib.models import OS_SNAME_LEN 

from django.utils.translation import ugettext_lazy as _

LOG = logging.getLogger(__name__)

class ProjectRequestForm(forms.SelfHandlingForm):

    prjaction = forms.ChoiceField(
        label=_('Project action'),
        choices = [
            ('newprj', _('Create personal project')),
            ('selprj', _('Select existing projects'))
        ],
        widget=forms.Select(attrs={
            'class': 'switchable',
            'data-slug': 'actsource'
        })
    )
    
    newprj = forms.CharField(
        label=_('Personal project'),
        max_length=OS_SNAME_LEN,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-newprj': _('Project name')
        })
    )
    prjdescr = forms.CharField(
        label=_("Project description"),
        required=False,
        widget=forms.widgets.Textarea(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-newprj': _('Project description')
        })
    )
    prjpriv = forms.BooleanField(
        label=_("Private project"),
        required=False,
        initial=False,
        widget=forms.widgets.CheckboxInput(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-newprj': _('Private project')
        })
    )
    
    selprj = forms.MultipleChoiceField(
        label=_('Available projects'),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'switched',
            'data-switch-on': 'actsource',
            'data-actsource-selprj': _('Select existing project')
        }),
    )


    notes = forms.CharField(
        label=_('Notes'),
        required=False,
        widget=forms.widgets.Textarea()
    )

    def __init__(self, *args, **kwargs):
        super(ProjectRequestForm, self).__init__(*args, **kwargs)

        auth_prjs = [
            pitem.name for pitem in self.request.user.authorized_tenants
        ]

        prj_list = Project.objects.exclude(projectname__in=auth_prjs)
        prj_list = prj_list.filter(status=PRJ_PUBLIC, projectid__isnull=False)

        self.fields['selprj'].choices = [
            (prj_entry.projectname, prj_entry.projectname) for prj_entry in prj_list
        ]

    @sensitive_variables('data')
    def handle(self, request, data):
    
        with transaction.commit_on_success():
        
            registration = Registration.objects.filter(userid=request.user.id)[0]
        
            prj_action = data['prjaction']
            prjlist = list()
            if prj_action == 'selprj':
                for project in data['selprj']:
                    prjlist.append((project, "", PRJ_PUBLIC, False))
            
            elif prj_action == 'newprj':
                prjlist.append((
                    data['newprj'],
                    data['prjdescr'],
                    PRJ_PRIVATE if data['prjpriv'] else PRJ_PUBLIC,
                    True
                ))

        
            for prjitem in prjlist:
        
                if prjitem[3]:
                    try:

                        prjArgs = {
                            'projectname' : prjitem[0],
                            'description' : prjitem[1],
                            'status' : prjitem[2]
                        }
                        project = Project.objects.create(**prjArgs)

                    except IntegrityError:
                        messages.error(request, _("Project %s already exists") % prjitem[0])
                        LOG.error("Cannot create project %s" % prjitem[0])
                        return False
                
                else:
                    project = Project.objects.get(projectname=prjitem[0])
                        
                reqArgs = {
                    'registration' : registration,
                    'project' : project,
                    'notes' : data['notes']
                }                
                reqPrj = PrjRequest(**reqArgs)
                reqPrj.save()

        return True



