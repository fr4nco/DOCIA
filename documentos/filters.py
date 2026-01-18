import django_filters
from django_filters import DateFilter
from .models import *
from core.models import *
from django import forms
from django_filters.widgets import RangeWidget
from django_filters import DateTimeFromToRangeFilter, BooleanFilter
from django.db import connection
from django.db.models import Q
from django.contrib.postgres.search import SearchVector, SearchQuery


class DocumentoFilter(django_filters.FilterSet):

    q = django_filters.CharFilter(
    label="Buscar por texto (asunto o texto extraído)",
    method="buscar_en_texto"
    )
    

    asunto = django_filters.CharFilter(
        label='Asunto',
        field_name='asunto',
        lookup_expr='icontains'
    )


    # Filtro por rango de fecha
    fecha_informe = django_filters.DateFromToRangeFilter(
        label="Fecha del informe (rango)",
        field_name='fecha_informe',
        widget=django_filters.widgets.RangeWidget(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )


    class Meta:
        model = Documento
        fields = [
            'dependencia', 'tipo_doc',
             'fecha_informe'
        ]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 🔹 filtrar solo dependencias policiales
        self.filters["dependencia"].queryset = (
            Dependencia.objects.filter(unidad__categoria_id=1)
        )

    def buscar_en_texto(self, queryset, name, value):
        engine = connection.settings_dict['ENGINE']

        if 'postgresql' in engine:
            return queryset.annotate(
                vector=SearchVector('asunto', 'texto_extraido')
            ).filter(vector=SearchQuery(value))
        else:
            return queryset.filter(
                Q(asunto__icontains=value) |
                Q(texto_extraido__icontains=value)
            )