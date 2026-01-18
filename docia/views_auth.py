from django.contrib.auth.views import LogoutView, LoginView, PasswordChangeView, PasswordResetConfirmView
from django.urls import reverse_lazy
from core.auditoria import registrar_auditoria
from core.models import Auditoria

class LoginAuditedView(LoginView):
    def form_valid(self, form):
        response = super().form_valid(form)
        registrar_auditoria(
            self.request,
            accion="LOGIN",
            modelo="Usuario",
            descripcion=f"Usuario {self.request.user.username} inició sesión",
        )
        return response


class LogoutAuditedView(LogoutView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            registrar_auditoria(
                request,
                accion="LOGOUT",
                modelo="Usuario",
                descripcion=f"Usuario {request.user.username} cerró sesión",
            )
        return super().dispatch(request, *args, **kwargs)


class PasswordChangeAuditedView(PasswordChangeView):
    success_url = reverse_lazy("password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        registrar_auditoria(
            self.request,
            accion="UPDATE",
            modelo="Usuario",
            descripcion=f"Usuario {self.request.user.username} cambió su contraseña",
        )
        return response


class PasswordResetConfirmAuditedView(PasswordResetConfirmView):
    def form_valid(self, form):
        response = super().form_valid(form)
        registrar_auditoria(
            self.request,
            accion="UPDATE",
            modelo="Usuario",
            descripcion=f"Usuario {self.user.username} recuperó la contraseña con token",
        )
        return response
