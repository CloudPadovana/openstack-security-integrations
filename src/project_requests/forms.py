import logging

from horizon import forms

from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from openstack_auth_shib.models import Registration
from openstack_auth_shib.models import Project
from openstack_auth_shib.models import PrjRequest

from openstack_auth_shib.models import PRJ_PUBLIC
from openstack_auth_shib.models import PRJ_PRIVATE

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

        avail_prjs = list()
        for prj_entry in Project.objects.filter(status=PRJ_PUBLIC):
            avail_prjs.append((prj_entry.projectname, prj_entry.projectname))

        self.fields['selprj'].choices = avail_prjs

    @sensitive_variables('data')
    def handle(self, request, data):
    
        with transaction.commit_on_success():
        
            registration = Registration.objects.filter(userid=request.user.id)[0]
        
            prj_action = data['prjaction']
            prjlist = list()
            if prj_action == 'selprj':
                for project in data['selprj']:
                    #
                    # TODO exclude tenants already subscribed
                    #
                    prjlist.append((project, "", PRJ_PUBLIC))
            
            elif prj_action == 'newprj':
                pers_prj = data['newprj']
                prj_descr = data['prjdescr']
                prj_vis = PRJ_PRIVATE if data['prjpriv'] else PRJ_PUBLIC
                prjlist.append((pers_prj, prj_descr, prj_vis))

        
            for prjitem in prjlist:
        
                try:
                
                    project = Project.objects.get(projectname=prjitem[0])
                
                except Project.DoesNotExist:
                    prjArgs = {
                        'projectname' : prjitem[0],
                        'description' : prjitem[1],
                        'status' : prjitem[2]
                    }
                    project = Project(**prjArgs)
                    project.save()
        
                reqArgs = {
                    'registration' : registration,
                    'project' : project,
                    'notes' : data['notes']
                }                
                reqPrj = PrjRequest(**reqArgs)
                reqPrj.save()

        return True



