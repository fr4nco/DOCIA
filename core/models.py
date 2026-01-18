# core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django_resized import ResizedImageField
from django.contrib.gis.db import models as gis_models
from django.conf import settings
from django.contrib.postgres.indexes import GistIndex
    
class Auditoria(models.Model):
    ACCIONES = [
        ("CREATE", "Creación"),
        ("UPDATE", "Modificación"),
        ("DELETE", "Eliminación"),
        ("VIEW", "Visualización"),
        ("SEARCH", "Búsqueda"),
        ("DOWNLOAD", "Descarga"),
        ("LOGIN", "Ingreso al sistema"),
        ("ASK", "Consulta a IA"),
        ("LOGOUT", "Salida del sistema"),
    ]
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Usuario"
    )
    accion = models.CharField(max_length=20, choices=ACCIONES)
    modelo = models.CharField(max_length=100)
    objeto_id = models.CharField(max_length=100, null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)

    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    navegador = models.CharField(max_length=50, blank=True)
    sistema_operativo = models.CharField(max_length=50, blank=True)
    dispositivo = models.CharField(max_length=50, blank=True)

    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha} - {self.usuario} - {self.accion} - {self.modelo}"
    

    




class CategoriaInstitucion(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Categoría de Institución")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name_plural = "Categorías de Instituciones"

    def __str__(self):
        return self.nombre
    


class Unidad(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Unidad/Institución")
    nombre_argos = models.CharField(max_length=150, unique=True, verbose_name="Nombre en Argos", null=True, blank=True)
    sigla = models.CharField(max_length=20, unique=True, verbose_name="Sigla", null=True, blank=True)
    categoria = models.ForeignKey(CategoriaInstitucion, on_delete=models.PROTECT, verbose_name="Categoría")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name_plural = "Unidades"

    def __str__(self):
        return self.nombre
    
class DependenciaArgos(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Dependencia en Argos")
    sigla = models.CharField(max_length=20, unique=True, verbose_name="Sigla", null=True, blank=True)
    unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT, verbose_name="Unidad")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name_plural = "Dependencias en Argos"

    def __str__(self):
        return self.nombre
    
class Dependencia(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Dependencia")
    dependencia_argos = models.ForeignKey(DependenciaArgos, on_delete=models.PROTECT, verbose_name="Dependencia en Argos", related_name="dependencias", null=True, blank=True)
    unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT, verbose_name="Unidad")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name_plural = "Dependencias"

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Equipo")
    dependencia = models.ForeignKey(Dependencia, on_delete=models.CASCADE, related_name="equipos")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name_plural = "Equipos"

    def __str__(self):
        return f"{self.dependencia} - {self.nombre}"


class TipoUsuario(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Tipo de Usuario")

    class Meta:
        verbose_name_plural = "Tipos de Usuarios"

    def __str__(self):
        return self.nombre
    
class TituloUsuario(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Título de Usuario")
    orden = models.PositiveIntegerField(default=1, verbose_name="Orden")
    categoria = models.ForeignKey(CategoriaInstitucion, on_delete=models.PROTECT, verbose_name="Categoría")

    class Meta:
        verbose_name_plural = "Títulos de Usuarios"

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    tipo_usuario = models.ForeignKey(TipoUsuario, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Tipo de Usuario")
    dependencia = models.ForeignKey(Dependencia, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Dependencia")
    titulo = models.ForeignKey(TituloUsuario, blank=True, null=True, on_delete=models.PROTECT, verbose_name="Título")
    equipos = models.ManyToManyField(Equipo, related_name="usuarios", verbose_name="Equipos", blank=True)

    class Meta:
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.titulo} {self.first_name} {self.last_name}"
    
    def get_nombre_completo_con_titulo(self):
        titulo = self.titulo.nombre if self.titulo else ""
        nombre = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return f"{titulo} {nombre}".strip()

