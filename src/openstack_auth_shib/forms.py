from django import forms
from django.forms.widgets import HiddenInput, PasswordInput

from django.utils.translation import ugettext_lazy as _

class BaseRegistForm(forms.Form):
    project = forms.CharField(label=_('Project'))
    notes = forms.CharField(label=_('Notes'))

class UsrPwdRegistForm(forms.Form):
    username = forms.CharField(label=_('Username'))
    pwd = forms.CharField(label=_('Password'), widget=PasswordInput)
    repwd = forms.CharField(label=_('Confirm password'), widget=PasswordInput)
    email = forms.EmailField(label=_('Email Address'))
    project = forms.CharField(label=_('Project'))
    notes = forms.CharField(label=_('Notes'))

