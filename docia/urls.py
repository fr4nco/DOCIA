"""
URL configuration for argos project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetCompleteView
from .views_auth import LogoutAuditedView,LoginAuditedView, PasswordChangeAuditedView, PasswordResetConfirmAuditedView


urlpatterns = [
      path("login/", LoginAuditedView.as_view(), name="login"),
    path("salir/", LogoutAuditedView.as_view(), name="salir"),

    # Cambio de contraseña
    path("password_change/", PasswordChangeAuditedView.as_view(), name="password_change"),
    path("password_change/done/", auth_views.PasswordResetDoneView.as_view(), name="password_change_done"),

    # Recuperar contraseña
    path("password_reset/", PasswordResetView.as_view(), name="password_reset"),
    path("password_reset/done/", PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", PasswordResetConfirmAuditedView.as_view(), name="password_reset_confirm"),
    path("reset/done/", PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    path('admin/', admin.site.urls),
    path('', include("core.urls")),
    path('documentos/', include('documentos.urls')),
 

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

