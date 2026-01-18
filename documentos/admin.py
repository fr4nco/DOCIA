# documentos/admin.py
from django.contrib import admin, messages
from .models import Documento, TipoDoc

@admin.action(description="Regenerar índice FAISS")
def regenerar_faiss_action(modeladmin, request, queryset):
    try:
        # 👇 Import diferido: solo cuando se ejecuta la acción
        from .faiss_utils import regenerar_indice_faiss
        regenerar_indice_faiss()
        messages.success(request, "✅ Índice FAISS regenerado correctamente.")
    except Exception as e:
        messages.error(request, f"❌ Error al regenerar índice FAISS: {e}")

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin): 
    list_display = ("id", "asunto", "fecha_informe", "creada_por")
    actions = [regenerar_faiss_action]

@admin.register(TipoDoc)
class TipoDocAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo")