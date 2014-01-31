from horizon import forms
from horizon.utils import validators

from django.forms import ValidationError
from django.utils.translation import ugettext_lazy as _

class BaseRegistForm(forms.Form):
    project = forms.CharField(label=_('Project'))
    notes = forms.CharField(label=_('Notes'))

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
    project = forms.CharField(label=_('Project'))
    notes = forms.CharField(label=_('Notes'))

    def clean(self):
        data = super(forms.Form, self).clean()
        if 'pwd' in data:
            if data['pwd'] != data.get('repwd', None):
                raise ValidationError(_('Passwords do not match.'))

        if '@' in data['username'] or ':' in data['username']:
                raise ValidationError(_("Invalid characters in user name (@:)"))

        return data

