from django.urls import path
from . import views
from .views import *


urlpatterns = [
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("auditoria/", AuditoriaListView.as_view(), name="auditoria_list"),
    path('', views.HomeView.as_view(), name='home'),
    


]