from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict
from core.middleware import get_current_request
from .auditoria import registrar_auditoria

MODELOS_A_AUDITAR = ["Evento", "Persona", "Documento"]

# Cacheamos valores viejos antes de guardar
@receiver(pre_save)
def cachear_valores_anteriores(sender, instance, **kwargs):
    if sender.__name__ not in MODELOS_A_AUDITAR or not instance.pk:
        return
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        instance._old_values = model_to_dict(old_instance)
    except sender.DoesNotExist:
        instance._old_values = {}

@receiver(post_save)
def auditar_guardado(sender, instance, created, **kwargs):
    if sender.__name__ not in MODELOS_A_AUDITAR:
        return
    request = get_current_request()
    if not request:
        return

    if created:
        descripcion = f"{sender.__name__} creado: {str(instance)}"
        accion = "CREATE"
    else:
        old_values = getattr(instance, "_old_values", {})
        new_values = model_to_dict(instance)
        cambios = []
        for campo, valor_anterior in old_values.items():
            valor_nuevo = new_values.get(campo)
            if valor_anterior != valor_nuevo:
                cambios.append(f"{campo}: '{valor_anterior}' → '{valor_nuevo}'")
        cambios_texto = "; ".join(cambios) if cambios else "Sin cambios relevantes"
        descripcion = f"{sender.__name__} modificado: {str(instance)} | {cambios_texto}"
        accion = "UPDATE"

    registrar_auditoria(
        request,
        accion,
        sender.__name__,
        objeto_id=str(instance.pk),
        descripcion=descripcion,
    )

@receiver(post_delete)
def auditar_borrado(sender, instance, **kwargs):
    if sender.__name__ not in MODELOS_A_AUDITAR:
        return
    request = get_current_request()
    if not request:
        return

    descripcion = f"{sender.__name__} eliminado: {str(instance)}"
    registrar_auditoria(
        request,
        "DELETE",
        sender.__name__,
        objeto_id=str(instance.pk),
        descripcion=descripcion,
    )
