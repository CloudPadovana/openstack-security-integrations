from django import forms
from django.forms.widgets import HiddenInput

class RegistrationForm(forms.Form):
    uname = forms.CharField(widget=HiddenInput)
    domain = forms.CharField(widget=HiddenInput)
    project = forms.CharField()


