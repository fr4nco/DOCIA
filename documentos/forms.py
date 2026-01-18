from django import forms
from .models import *
from core.models import *
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from leaflet.forms.widgets import LeafletWidget

class DocumentoForm(forms.ModelForm):

    class Meta:
        model = Documento
        exclude = ( 'fecha_ingresada',)
        fields = [
            "dependencia",
            "descripcion", "tipo_doc", "fecha_informe",
            "asunto", "informe", "informe_editable", "leido_por_ia",
        ]
        widgets = {
            'fecha_informe': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d'  # 👈 ¡Esto es lo que faltaba!
            ),
        }

    def __init__(self, *args, **kwargs):
        super(DocumentoForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            existing_classes = visible.field.widget.attrs.get('class', '')
            visible.field.widget.attrs['class'] = f'{existing_classes} mi-selector form-control'