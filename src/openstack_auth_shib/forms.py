import logging

from horizon import forms
from horizon.utils import validators

from django.forms import ValidationError
from django.utils.translation import ugettext as _

from .models import Project
from .models import PRJ_PUBLIC

LOG = logging.getLogger(__name__)

#
# TODO check form field length
#

class BaseRegistForm(forms.Form):

    prjaction = forms.ChoiceField(
        label=_('Project action'),
        choices=[
            ('newprj', _('Create personal project')),
            ('selprj', _('Select existing projects')),
            ('guestprj', _('Use guest project'))
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
        super(BaseRegistForm, self).__init__(*args, **kwargs)
        
        avail_prjs = list()
        for prj_entry in Project.objects.filter(status=PRJ_PUBLIC):
            avail_prjs.append((prj_entry.projectname, prj_entry.projectname))
        self.fields['selprj'].choices = avail_prjs
    
    def clean(self):
        data = super(BaseRegistForm, self).clean()
        if data['prjaction'] == 'newprj':
            if not data['newprj']:
                raise ValidationError(_('Project name is required.'))
        elif data['prjaction'] == 'selprj':
            if not data['selprj']:
                raise ValidationError(_('Missing selected project.'))
        elif data['prjaction'] <> 'guestprj':
            raise ValidationError(_('Wrong project parameter.'))
        return data

class UsrPwdRegistForm(forms.Form):
    username = forms.CharField(label=_('User name'))
    fullname = forms.CharField(label=_('Full name'))
    pwd = forms.RegexField(
        label=_("Password"),
        widget=forms.PasswordInput(render_value=False),
        regex=validators.password_validator(),
        error_messages={'invalid': validators.password_validator_msg()})
    repwd = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(render_value=False))
    email = forms.EmailField(label=_('Email Address'))
    
    def clean(self):
        data = super(UsrPwdRegistForm, self).clean()
        if 'pwd' in data:
            if data['pwd'] != data.get('repwd', None):
                raise ValidationError(_('Passwords do not match.'))

        if '@' in data['username'] or ':' in data['username']:
                raise ValidationError(_("Invalid characters in user name (@:)"))

        return data

class FullRegistForm(UsrPwdRegistForm, BaseRegistForm):

    def clean(self):
        data = BaseRegistForm.clean(self)
        data.update(UsrPwdRegistForm.clean(self))
        return data




