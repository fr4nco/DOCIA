import os
from django.db import models
from core.models import Dependencia, Usuario
from .utils import extraer_texto_pdf


class TipoDoc(models.Model):
    tipo = models.CharField(
        max_length=40, verbose_name="Tipo de Documento", unique=True
    )

    class Meta:
        verbose_name_plural = "Tipos de Documentos"

    def __str__(self):
        return self.tipo


class Documento(models.Model):
    dependencia = models.ForeignKey(
        Dependencia,
        verbose_name="Área/Departamento",
        on_delete=models.CASCADE,
    )
    leido_por_ia = models.BooleanField(verbose_name="Leído por IA", default=False)

    creada_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Creado por",
    )
    descripcion = models.TextField(
        verbose_name="Descripción", null=True, blank=True, default=""
    )
    tipo_doc = models.ForeignKey(
        TipoDoc, verbose_name="Tipo de documento", on_delete=models.CASCADE
    )
    fecha_informe = models.DateField(verbose_name="Fecha del Informe")
    asunto = models.CharField(max_length=220, verbose_name="Asunto")
    informe = models.FileField(
        upload_to="documento/informes/", null=True, verbose_name="Informe"
    )
    informe_editable = models.FileField(
        upload_to="documento/informes_editables/",
        null=True,
        blank=True,
        verbose_name="Informe Editable (opcional)",
    )
    texto_extraido = models.TextField(
        blank=True,
        null=True,
        editable=True,
        verbose_name="Texto extraído automáticamente",
    )
    fecha_ingresada = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Ingreso"
    )
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Documentos"
        ordering = ["-fecha_ingresada"]
        permissions = [
            ("puede_preguntar_ia", "Puede realizar consultas de IA sobre documentos"),
        ]

    def save(self, *args, **kwargs):
        nuevo = self._state.adding
        texto_antes, asunto_antes, desc_antes = None, None, None

        if not nuevo:
            try:
                anterior = Documento.objects.get(pk=self.pk)
                texto_antes = anterior.texto_extraido
                asunto_antes = anterior.asunto
                desc_antes = anterior.descripcion
            except Documento.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # 🔹 Si hay PDF pero no texto, extraerlo
        if self.informe and not self.texto_extraido:
            ruta = self.informe.path
            if os.path.exists(ruta):
                texto = extraer_texto_pdf(ruta)
                if texto:
                    self.texto_extraido = texto.strip()
                    super().save(update_fields=["texto_extraido"])

        # 🔹 Reindexar en FAISS si:
        #   - Documento nuevo
        #   - O cambió el texto_extraido
        #   - O cambió el asunto
        #   - O cambió la descripción
        if (
            self.texto_extraido and (
                nuevo or
                self.texto_extraido != texto_antes or
                self.asunto != asunto_antes or
                self.descripcion != desc_antes
            )
        ):
            try:
                from documentos.faiss_utils import eliminar_fragmentos_por_doc, agregar_fragmentos_doc
                eliminar_fragmentos_por_doc(self.id)   # Limpia lo viejo
                agregar_fragmentos_doc(self.id)        # Indexa lo nuevo
                print(f"✅ Documento {self.id} reindexado en FAISS")
            except Exception as e:
                print(f"⚠️ Error al indexar documento {self.id}: {e}")


    def fecha_formateada(self):
        if self.fecha_informe:
            return self.fecha_informe.strftime("%d/%m/%Y")
        return "Sin fecha"

    def __str__(self):
        return f"{self.fecha_formateada()} - {self.asunto or 'Sin Asunto'}"

    def delete(self, using=None, keep_parents=False):
        from documentos.faiss_utils import eliminar_fragmentos_por_doc
        eliminar_fragmentos_por_doc(self.id)

        if self.informe:
            self.informe.storage.delete(self.informe.name)
        if self.informe_editable:
            self.informe_editable.storage.delete(self.informe_editable.name)

        super().delete(using, keep_parents)
