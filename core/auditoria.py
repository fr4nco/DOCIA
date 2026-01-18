# core/auditoria.py
from functools import wraps
from .models import Auditoria
from django_user_agents.utils import get_user_agent

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")

def registrar_auditoria(origen, accion, modelo, objeto_id=None, descripcion=""):
    """
    Registra una acción de auditoría.
    Puede recibir tanto un 'request' como directamente un 'usuario'.
    """
    try:
        # Determinar si origen es un request o un usuario
        if hasattr(origen, "user"):  # si es un HttpRequest
            request = origen
            usuario = request.user if request.user.is_authenticated else None
            ip = get_client_ip(request)
            ua = get_user_agent(request)
            navegador = ua.browser.family
            so = ua.os.family
            dispositivo = ua.device.family
        else:
            # Si es un objeto Usuario
            usuario = origen if getattr(origen, "is_authenticated", False) else None
            ip = "N/A"
            navegador = "N/A"
            so = "N/A"
            dispositivo = "N/A"

        print(f"📌 Auditoría: {accion} {modelo} {objeto_id} - {descripcion}")

        Auditoria.objects.create(
            usuario=usuario,
            accion=accion,
            modelo=modelo,
            objeto_id=objeto_id,
            descripcion=descripcion,
            ip_origen=ip,
            navegador=navegador,
            sistema_operativo=so,
            dispositivo=dispositivo,
        )
    except Exception as e:
        print(f"[AUDITORIA] Error al registrar auditoría: {e}")

def auditar_vista(accion, descripcion=""):
    """
    Decorador para auditar vistas basadas en clases (DetailView).
    Detecta automáticamente el modelo y el __str__ del objeto.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            response = func(self, request, *args, **kwargs)

            try:
                obj = getattr(self, "object", None)
                if obj:
                    modelo = obj.__class__.__name__
                    objeto_id = str(obj.pk)
                    objeto_str = str(obj)
                else:
                    modelo = self.__class__.__name__
                    objeto_id = kwargs.get("pk")
                    objeto_str = f"ID {objeto_id}"

                desc_final = f"{descripcion}: {objeto_str}" if descripcion else f"{accion} de {objeto_str}"

                registrar_auditoria(
                    request,
                    accion,
                    modelo,
                    objeto_id=objeto_id,
                    descripcion=desc_final
                )
            except Exception as e:
                print(f"[AUDITORIA] Error al registrar auditoría: {e}")

            return response
        return wrapper
    return decorator
