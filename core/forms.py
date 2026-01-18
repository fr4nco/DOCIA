from django import forms
from .models import *
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from leaflet.forms.widgets import LeafletWidget

class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

