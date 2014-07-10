import logging

from horizon import forms
from horizon.utils import validators

from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import ugettext as _

from .models import Project
from .models import PRJ_PRIVATE, PRJ_GUEST
from .models import OS_LNAME_LEN, OS_SNAME_LEN, PWD_LEN, EMAIL_LEN
from .utils import import_guest_project

LOG = logging.getLogger(__name__)

class MixRegistForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(MixRegistForm, self).__init__(*args, **kwargs)
        
        initial = kwargs['initial'] if 'initial' in kwargs else dict()
        self.isFullForm = 'ftype' in initial and initial['ftype'] == 'full'
        
        if self.isFullForm:
            self.fields['username'] = forms.CharField(
                label=_('User name'),
                max_length=OS_LNAME_LEN
            )
            
        if self.isFullForm or 'givenname' in initial:
            self.fields['givenname'] = forms.CharField(
                label=_('First name'),
                max_length=OS_LNAME_LEN,
                widget=forms.HiddenInput if 'givenname' in initial else forms.TextInput
            )
            
        if self.isFullForm or 'sn' in initial:
            self.fields['sn'] = forms.CharField(
                label=_('Last name'),
                max_length=OS_LNAME_LEN,
                widget=forms.HiddenInput if 'sn' in initial else forms.TextInput
            )
            
        if self.isFullForm:
            self.fields['pwd'] = forms.RegexField(
                label=_("Password"),
                max_length=PWD_LEN,
                widget=forms.PasswordInput(render_value=False),
                regex=validators.password_validator(),
                error_messages={'invalid': validators.password_validator_msg()}
            )
            
            self.fields['repwd'] = forms.CharField(
                label=_("Confirm Password"),
                max_length=PWD_LEN,
                widget=forms.PasswordInput(render_value=False)
            )
            
            self.fields['email'] = forms.EmailField(
                label=_('Email Address'),
                max_length=EMAIL_LEN
            )
        
        self.fields['prjaction'] = forms.ChoiceField(
            label=_('Project action'),
            #choices = <see later>
            widget=forms.Select(attrs={
                'class': 'switchable',
                'data-slug': 'actsource'
            })
        )
    
        self.fields['newprj'] = forms.CharField(
            label=_('Personal project'),
            max_length=OS_SNAME_LEN,
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Project name')
            })
        )
        
        self.fields['prjdescr'] = forms.CharField(
            label=_("Project description"),
            required=False,
            widget=forms.widgets.Textarea(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Project description')
            })
        )
        
        self.fields['prjpriv'] = forms.BooleanField(
            label=_("Private project"),
            required=False,
            initial=False,
            widget=forms.widgets.CheckboxInput(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-newprj': _('Private project')
            })
        )
    
        self.fields['selprj'] = forms.MultipleChoiceField(
            label=_('Available projects'),
            required=False,
            widget=forms.SelectMultiple(attrs={
                'class': 'switched',
                'data-switch-on': 'actsource',
                'data-actsource-selprj': _('Select existing project')
            }),
        )

        self.fields['organization'] = forms.CharField(
            label=_('Organization'),
            required=True
        )
    
        phone_regex = settings.HORIZON_CONFIG.get('phone_regex', '^\s*\+*[0-9]+[0-9\s.]+\s*$')
        self.fields['phone'] = forms.RegexField(
            label=_('Phone number'),
            required=True,
            regex=phone_regex,
            error_messages={'invalid': _("Wrong phone format")}
        )
    
        self.fields['contactper'] = forms.CharField(
            label=_('Contact person'),
            required=False
        )
    
        self.fields['notes'] = forms.CharField(
            label=_('Notes'),
            required=False,
            widget=forms.widgets.Textarea()
        )
    
        self.fields['aupok'] = forms.CharField(
            widget=forms.HiddenInput,
            initial='reject'
        )

        import_guest_project()
        
        missing_guest = True
        avail_prjs = list()
        for prj_entry in Project.objects.exclude(status=PRJ_PRIVATE):
            if prj_entry.status == PRJ_GUEST:
                missing_guest = False
            elif prj_entry.projectid:
                avail_prjs.append((prj_entry.projectname, prj_entry.projectname))
                
        self.fields['selprj'].choices = avail_prjs
        
        if missing_guest:
            p_choices = [
                ('newprj', _('Create new project')),
                ('selprj', _('Select existing projects'))
            ]
        else:
            p_choices = [
                ('newprj', _('Create new project')),
                ('selprj', _('Select existing projects')),
                ('guestprj', _('Use guest project'))
            ]
            
        self.fields['prjaction'].choices = p_choices



    def clean(self):
        data = super(MixRegistForm, self).clean()
        
        if data['prjaction'] == 'newprj':
            if not data['newprj']:
                raise ValidationError(_('Project name is required.'))
        elif data['prjaction'] == 'selprj':
            if not data['selprj']:
                raise ValidationError(_('Missing selected project.'))
        elif data['prjaction'] <> 'guestprj':
            raise ValidationError(_('Wrong project parameter.'))
        
        if data.get('aupok', 'reject') <> 'accept':
            raise ValidationError(_('You must accept Cloud Padovana AUP.'))
            
        if self.isFullForm:
            if 'pwd' in data:
                if data['pwd'] != data.get('repwd', None):
                    raise ValidationError(_('Passwords do not match.'))

            if '@' in data['username'] or ':' in data['username']:
                raise ValidationError(_("Invalid characters in user name (@:)"))
        
        return data


