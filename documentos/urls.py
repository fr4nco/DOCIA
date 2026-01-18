from django.urls import path
from .views import *
from . import views


urlpatterns = [
    path("", DocumentosListView.as_view(), name="documentos"),
    path("documento/crear", CrearDocumentoView.as_view(), name="crear_documento"),
    path(
        "documento/editar/<int:id>",
        EditarDocumentoView.as_view(),
        name="editar_documento",
    ),
    path("documento/ver/<int:id>", VerDocumentoView.as_view(), name="ver_documento"),
    path(
        "eliminar/documento/<int:id>",
        EliminarDocumentoView.as_view(),
        name="eliminar_documento",
    ),
    path("preguntar/", views.preguntar_argos_html, name="preguntar_argos_link"),
    path("preguntar-argos/", views.preguntar_argos, name="preguntar_argos"),
    path("buscar-faiss/", views.buscar_con_faiss, name="buscar_con_faiss"),
]
