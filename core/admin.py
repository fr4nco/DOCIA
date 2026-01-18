from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin

admin.site.site_header = "Administración de DOCIA"
admin.site.site_title = "Panel DOCIA"
admin.site.index_title = "Bienvenido al sistema DOCIA"

@admin.register(CategoriaInstitucion)
class CategoriaInstitucionAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)

@admin.register(Calibre)
class CalibreAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)
    
@admin.register(TipoLugar)
class TipoLugarAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)

@admin.register(EstadoEvidencia)
class EstadoEvidenciaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)

@admin.register(Operativo)
class OperativoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "dependencia",)
    search_fields = ("nombre",)

@admin.register(TipoActuacion)
class TipoActuacionAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)

@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)



# Institución
@admin.register(Unidad)
class UnidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "descripcion")
    list_filter = ("categoria",)
    search_fields = ("nombre",)
    
# Dependencia
@admin.register(Dependencia)
class DependenciaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad", "descripcion")
    list_filter = ("unidad",)
    search_fields = ("nombre",)    


# Equipo
@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "dependencia", "descripcion")
    list_filter = ("dependencia",)
    search_fields = ("nombre", "dependencia__nombre")


@admin.register(TipoUsuario)
class TipoUsuarioAdmin(admin.ModelAdmin):
    list_display = ("nombre",)

@admin.register(TituloUsuario)
class TituloUsuarioAdmin(admin.ModelAdmin):
    list_display = ("nombre",)

@admin.register(DependenciaArgos)
class DependenciaArgosAdmin(admin.ModelAdmin):
    list_display = ("nombre","sigla", "unidad")
    search_fields = ("nombre", "sigla")

# Usuario
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Información Adicional", {
            "fields": ("tipo_usuario", "titulo", "dependencia", "equipos")
        }),
    )

    list_display = ("username", "first_name", "last_name", "email", "tipo_usuario", "titulo")
    list_filter = ("tipo_usuario", "titulo", "equipos")
    search_fields = ("username", "first_name", "last_name", "email")
    filter_horizontal = ("groups", "user_permissions", "equipos")  # soporte a muchos equipos
