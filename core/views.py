from pyexpat.errors import messages
from django.forms import DurationField
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db import connection
from django.db.models import FloatField, F, IntegerField,Avg, Count, ExpressionWrapper, DurationField
from django.db.models.functions import Abs, Cast, Round, ExtractMonth, TruncMonth, ExtractWeekDay, ExtractHour, ExtractDay
from django.contrib.gis.db.models import GeometryField, Union
from django.contrib.gis.db.models.functions import Distance, AsGeoJSON, Transform, Centroid, Intersection
from django.contrib.gis.geos import Point, Polygon
from django.db.models import Func
from statistics import mean
import json
from django.contrib.gis.measure import D
from collections import defaultdict,OrderedDict, defaultdict
from datetime import date, datetime, timedelta
from core.models import Direccion, RedVial, Localidad, Departamento, Seccional, Equipo, Auditoria, Usuario
import calendar, locale, traceback, os, re, csv, json
from django.utils import timezone
import django_filters
from django_filters import DateFilter
from django.db.models import Count, Sum, F, FloatField, ExpressionWrapper, Value
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.paginator import Paginator

from documentos.filters import DocumentoFilter
from documentos.models import Documento



@login_required
def equipos_por_dependencia(request, dependencia_id):
    equipos = Equipo.objects.filter(dependencia_id=dependencia_id)
    opciones = '<option value="">Seleccione un equipo</option>'
    for equipo in equipos:
        opciones += f'<option value="{equipo.id}">{equipo.nombre}</option>'
    return HttpResponse(opciones)

# ============================================================
# Funcs auxiliares PostGIS
# ============================================================

class CollectionExtract(Func):
    function = "ST_CollectionExtract"
    output_field = GeometryField()

class SimplifyPreserveTopology(Func):
    function = "ST_SimplifyPreserveTopology"
    output_field = GeometryField()

def _parse_bbox(q):
    """Parsea bounding box x,y,x,y a Polygon GEOS."""
    try:
        a = [float(x) for x in q.split(",")]
        if len(a) != 4:
            return None
        return Polygon.from_bbox((a[0], a[1], a[2], a[3]))
    except Exception:
        return None


# ============================================================
# Autocomplete de calles (para input con 3+ caracteres)
# ============================================================

class BuscarCalleView(View):
    def get(self, request, departamento_id):
        q = request.GET.get("q", "").strip()
        if len(q) < 3:
            return JsonResponse([], safe=False)

        calles = (
            RedVial.objects
            .filter(departamento_fk_id=departamento_id, nombre__icontains=q)
            .values("idcalle", "nombre", "localidad")
            .distinct()[:20]
        )

        results = []
        for c in calles:
            texto = c["nombre"]
            if c["localidad"]:
                texto = f"{c['nombre']} ({c['localidad']})"
            results.append({
                "idcalle": c["idcalle"],
                "nombre": texto
            })
        return JsonResponse(results, safe=False)
    
class DetalleCalleView(View):
    def get(self, request, calle_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                  ST_AsGeoJSON(ST_SimplifyPreserveTopology(ST_Union(geom), 1)) AS geom,
                  ST_Y(ST_Centroid(ST_Union(geom))) AS lat,
                  ST_X(ST_Centroid(ST_Union(geom))) AS lon,
                  MAX(nombre) AS nombre
                FROM core_redvial
                WHERE idcalle = %s
            """, [calle_id])
            row = cursor.fetchone()

        if not row or not row[0]:
            return JsonResponse({"error": "Calle no encontrada"}, status=404)

        return JsonResponse({
            "lat": row[1],
            "lon": row[2],
            "nombre": row[3],
            "geom": json.loads(row[0])
        })
    

class BuscarEsquinaView(View):
    def get(self, request, departamento_id, calle_id):
        q = request.GET.get("q", "").strip()
        if len(q) < 3:
            return JsonResponse([], safe=False)

        # obtener calle base
        try:
            calle_base = RedVial.objects.get(id=calle_id)
        except RedVial.DoesNotExist:
            return JsonResponse([], safe=False)

        # buscamos coincidencias de nombre en ese departamento
        calles = (
            RedVial.objects
            .filter(
                departamento_fk_id=departamento_id,
                nombre__icontains=q.upper()  # forzar comparación en mayúsculas
            )
            .exclude(nombre=calle_base.nombre)
            .annotate(centro=Centroid("geom"))
            .values("id", "nombre", "localidad", "departamento_fk__nombre", "centro")
        )

        agrupados = defaultdict(lambda: {"ids": [], "localidad": None, "departamento": None, "coords": []})

        for c in calles:
            agrupados[c["nombre"]]["ids"].append(c["id"])
            agrupados[c["nombre"]]["localidad"] = c["localidad"]
            agrupados[c["nombre"]]["departamento"] = c["departamento_fk__nombre"]
            if c["centro"]:
                agrupados[c["nombre"]]["coords"].append((c["centro"].x, c["centro"].y))

        results = []
        for nombre, datos in agrupados.items():
            lon = sum(x for x, _ in datos["coords"]) / len(datos["coords"]) if datos["coords"] else None
            lat = sum(y for _, y in datos["coords"]) / len(datos["coords"]) if datos["coords"] else None

            results.append({
                "ids": datos["ids"],
                "nombre": nombre,
                "localidad": datos["localidad"],
                "departamento": datos["departamento"],
                "lat": lat,
                "lon": lon,
            })

        return JsonResponse(results, safe=False)
    
class DetalleEsquinaView(View):
    def get(self, request, calle_id, esquina_id):
        # nombre de la calle base
        with connection.cursor() as cursor:
            cursor.execute("SELECT nombre FROM core_redvial WHERE id=%s", [calle_id])
            row = cursor.fetchone()
        if not row:
            return JsonResponse({"error": "No se encontró la calle base"}, status=404)

        nombre_calle = row[0]

        # intersección con cualquier tramo de la calle base
        sql = """
            SELECT ST_AsGeoJSON(ST_Intersection(c1.geom, c2.geom)) as interseccion
            FROM core_redvial c1, core_redvial c2
            WHERE c1.nombre = %s
              AND c2.id = %s
              AND c1.departamento_fk_id = c2.departamento_fk_id
              AND ST_Intersects(c1.geom, c2.geom)
            LIMIT 1;
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [nombre_calle, esquina_id])
            row = cursor.fetchone()

        if not row or not row[0]:
            return JsonResponse({"error": "No se encontró intersección"}, status=404)

        interseccion = json.loads(row[0])

        # obtener punto
        if interseccion["type"] == "Point":
            coords = interseccion["coordinates"]
        else:
            sql_centroid = "SELECT ST_AsGeoJSON(ST_Centroid(ST_GeomFromGeoJSON(%s)))"
            with connection.cursor() as cursor:
                cursor.execute(sql_centroid, [json.dumps(interseccion)])
                centroid = cursor.fetchone()[0]
            coords = json.loads(centroid)["coordinates"]

        return JsonResponse({
            "lat": coords[1],
            "lon": coords[0]
        })
        
class DetalleEsquinaExactaView(View):
    def get(self, request, calle_id, esquina_id):
        try:
            calle1 = RedVial.objects.get(id=calle_id)
            calle2 = RedVial.objects.get(id=esquina_id)
        except RedVial.DoesNotExist:
            return JsonResponse({"error": "Alguna de las calles no existe"}, status=404)

        interseccion = calle1.geom.intersection(calle2.geom)

        if interseccion.empty:
            return JsonResponse({"error": "No hay intersección geométrica"}, status=404)

        # Si es un Point: devolver coordenadas
        if interseccion.geom_type == "Point":
            return JsonResponse({
                "lat": interseccion.y,
                "lon": interseccion.x,
                "geom": interseccion.geojson,
            })

        # Si es LineString o MultiLineString: agarrar centroide
        return JsonResponse({
            "lat": interseccion.centroid.y,
            "lon": interseccion.centroid.x,
            "geom": interseccion.geojson,
        })

@require_GET
@csrf_exempt
def buscar_direccion(request):
    idcalle = request.GET.get("idcalle")
    numero = request.GET.get("numero", "").strip()

    if not idcalle:
        return JsonResponse({"error": "Debe seleccionar una calle"}, status=400)

    try:
        # Buscar tramo de calle
        calle = RedVial.objects.filter(idcalle=idcalle).first()
        if not calle:
            return JsonResponse({"error": "Calle no encontrada"}, status=404)

        # Caso 1: número exacto
        if numero:
            direccion = (
                Direccion.objects
                .filter(nombre_via__icontains=calle.nombre, num_puerta=numero)
                .first()
            )
            if direccion:
                return JsonResponse({
                    "lat": direccion.latitud,
                    "lon": direccion.longitud,
                    "via": direccion.nombre_via,
                    "num": direccion.num_puerta,
                    "aproximada": False,
                })

            # Fallback: devolver centroide de la calle
            centro = calle.geom.centroid
            return JsonResponse({
                "lat": centro.y,
                "lon": centro.x,
                "via": calle.nombre,
                "num": numero,
                "aproximada": True,
            })

        # Caso 2: solo calle
        centro = calle.geom.centroid
        return JsonResponse({
            "lat": centro.y,
            "lon": centro.x,
            "via": calle.nombre,
            "aproximada": True,
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# ============================================================
# Geocodificación inversa: coordenadas → atributos
# ============================================================

@require_GET
def geocodificar_inversa(request):
    try:
        lat = float(request.GET.get("lat"))
        lon = float(request.GET.get("lon"))
        punto = Point(lon, lat, srid=4326)

        via = (
            RedVial.objects
            .annotate(distancia=Distance('geom', punto))
            .order_by('distancia')
            .first()
        )

        loc = (
            Localidad.objects
            .annotate(distancia=Distance('geom', punto))
            .order_by('distancia')
            .first()
        )

        secc = (
            Seccional.objects
            .annotate(distancia=Distance('geom', punto))
            .order_by('distancia')
            .first()
        )

        depto = (
            Departamento.objects
            .annotate(distancia=Distance('geom', punto))
            .order_by('distancia')
            .first()
        )

        return JsonResponse({
            "via": via.nombre if via else None,
            "idcalle": via.idcalle if via else None,
            "localidad": loc.nombre if loc else None,
            "seccional": secc.nombre if secc else None,
            "departamento": depto.nombre if depto else None,
            "lat": lat,
            "lon": lon,
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def departamento_bbox(request, depto_id):
    try:
        depto = Departamento.objects.get(id=depto_id)
        if depto.geom:
            xmin, ymin, xmax, ymax = depto.geom.extent  # bounding box
            return JsonResponse({
                "bbox": [xmin, ymin, xmax, ymax]
            })
        else:
            return JsonResponse({"error": "El departamento no tiene geometría"}, status=404)
    except Departamento.DoesNotExist:
        return JsonResponse({"error": "Departamento no encontrado"}, status=404)

# ============================================================
# Vector Tiles (MVT) para Leaflet VectorGrid
# ============================================================

def departamentos_mvt(request, z, x, y):
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH bounds AS (SELECT ST_TileEnvelope(%s,%s,%s) AS geom),
            mvtgeom AS (
              SELECT d.id, d.nombre,
                ST_AsMVTGeom(ST_Transform(d.geom,3857), bounds.geom, 4096, 256, true) AS geom
              FROM core_departamento d, bounds
              WHERE ST_Intersects(ST_Transform(d.geom,3857), bounds.geom)
            )
            SELECT ST_AsMVT(mvtgeom,'departamentos',4096,'geom') FROM mvtgeom;
        """, [z, x, y])
        tile = cursor.fetchone()[0]
    return HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")


@require_GET
def localidades_mvt(request, z, x, y):
    z = int(z)
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH bounds AS (SELECT ST_TileEnvelope(%s,%s,%s) AS geom),
            mvtgeom AS (
              SELECT l.id, l.nombre, d.nombre AS departamento,
                ST_AsMVTGeom(
                  CASE
                    WHEN %s < 8 THEN ST_SimplifyPreserveTopology(ST_Transform(l.geom,3857), 2000)
                    WHEN %s < 12 THEN ST_SimplifyPreserveTopology(ST_Transform(l.geom,3857), 500)
                    ELSE ST_Transform(l.geom,3857)
                  END,
                  bounds.geom, 4096, 256, true
                ) AS geom
              FROM core_localidad l
              LEFT JOIN core_departamento d ON l.departamento_id = d.id,
                   bounds
              WHERE ST_Intersects(ST_Transform(l.geom,3857), bounds.geom)
            )
            SELECT ST_AsMVT(mvtgeom, 'localidades', 4096, 'geom') FROM mvtgeom;
        """, [z, x, y, z, z])
        tile = cursor.fetchone()[0]
    return HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")


def cargar_localidades(request):
    depto_id = request.GET.get("depto_id")
    localidades = Localidad.objects.filter(departamento=depto_id).order_by("nombre")
    data = [{"id": loc.id, "nombre": loc.nombre} for loc in localidades]
    return JsonResponse(data, safe=False)


def seccionales_mvt(request, z, x, y, departamento_id=None):
    with connection.cursor() as cursor:
        query = """
            WITH bounds AS (SELECT ST_TileEnvelope(%s,%s,%s) AS geom),
            mvtgeom AS (
              SELECT s.id, s.nombre, s.seccion,
                ST_AsMVTGeom(ST_Transform(s.geom,3857), bounds.geom, 4096, 256, true) AS geom
              FROM core_seccional s, bounds
              WHERE ST_Intersects(ST_Transform(s.geom,3857), bounds.geom)
        """
        params = [z, x, y]
        if departamento_id:
            query += " AND s.departamento_id = %s"
            params.append(departamento_id)
        query += ") SELECT ST_AsMVT(mvtgeom,'seccionales',4096,'geom') FROM mvtgeom;"
        cursor.execute(query, params)
        tile = cursor.fetchone()[0]
    return HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")


def vias_mvt(request, z, x, y, departamento_id=None):
    with connection.cursor() as cursor:
        query = """
            WITH bounds AS (SELECT ST_TileEnvelope(%s,%s,%s) AS geom),
            mvtgeom AS (
              SELECT r.idcalle, r.nombre, r.tipo_vialidad,
                ST_AsMVTGeom(ST_Transform(r.geom,3857), bounds.geom, 4096, 256, true) AS geom
              FROM core_redvial r, bounds
              WHERE ST_Intersects(ST_Transform(r.geom,3857), bounds.geom)
        """
        params = [z, x, y]
        if departamento_id:
            query += " AND r.departamento_fk_id = %s"
            params.append(departamento_id)
        query += ") SELECT ST_AsMVT(mvtgeom,'vias',4096,'geom') FROM mvtgeom;"
        cursor.execute(query, params)
        tile = cursor.fetchone()[0]
    return HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")

def vias_por_departamento_mvt(request, depto_id, z, x, y):
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH bounds AS (SELECT ST_TileEnvelope(%s,%s,%s) AS geom),
            mvtgeom AS (
              SELECT r.idcalle, r.nombre, r.tipo_vialidad,
                ST_AsMVTGeom(ST_Transform(r.geom,3857), bounds.geom, 4096, 256, true) AS geom
              FROM core_redvial r
              JOIN core_departamento d ON ST_Intersects(r.geom, d.geom)
              , bounds
              WHERE d.id = %s
              AND ST_Intersects(ST_Transform(r.geom,3857), bounds.geom)
            )
            SELECT ST_AsMVT(mvtgeom,'vias',4096,'geom') FROM mvtgeom;
        """, [z, x, y, depto_id])
        tile = cursor.fetchone()[0]
    return HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")


def seccionales_por_departamento_mvt(request, depto_id, z, x, y):
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH bounds AS (SELECT ST_TileEnvelope(%s,%s,%s) AS geom),
            mvtgeom AS (
              SELECT s.id, s.nombre, s.seccion,
                ST_AsMVTGeom(ST_Transform(s.geom,3857), bounds.geom, 4096, 256, true) AS geom
              FROM core_seccional s
              JOIN core_departamento d ON ST_Intersects(s.geom, d.geom)
              , bounds
              WHERE d.id = %s
              AND ST_Intersects(ST_Transform(s.geom,3857), bounds.geom)
            )
            SELECT ST_AsMVT(mvtgeom,'seccionales',4096,'geom') FROM mvtgeom;
        """, [z, x, y, depto_id])
        tile = cursor.fetchone()[0]
    return HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")



# Configurar locale
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.utf8')
except locale.Error:
    pass



class HomeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'documentos.view_documento'
    login_url = '/login'
    template_name = "documentos/index.html"
    paginate_by = 18

    def get(self, request, *args, **kwargs):
        documentos = DocumentoFilter(
            request.GET, queryset=Documento.objects.all().order_by("-fecha_informe")
        )
        paginator = Paginator(documentos.qs, self.paginate_by)
        page_number = request.GET.get('pagina')
        page_obj = paginator.get_page(page_number)
        return render(request, self.template_name, {
            "filtro": documentos,
            "objetos": page_obj,
        })

class OficialesPorEquipoView(View):
    def get(self, request, equipo_id):
        oficiales = Usuario.objects.filter(equipos__id=equipo_id).values("id","titulo__nombre", "first_name", "last_name")
        data = [
            {"id": o["id"], "nombre": f"{o['titulo__nombre']} {o['first_name']} {o['last_name']}"}
            for o in oficiales
        ]
        return JsonResponse(data, safe=False)
    
class AuditoriaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Auditoria
    template_name = "core/auditoria_list.html"
    context_object_name = "auditorias"
    paginate_by = 40
    permission_required = "core.view_auditoria"

    def get_queryset(self):
        qs = Auditoria.objects.select_related("usuario").order_by("-fecha")

        # filtros opcionales desde GET
        accion = self.request.GET.get("accion")
        if accion:
            qs = qs.filter(accion=accion)

        usuario = self.request.GET.get("usuario")
        if usuario:
            qs = qs.filter(usuario__username__icontains=usuario)

        descripcion = self.request.GET.get("descripcion")
        if descripcion:
            qs = qs.filter(descripcion__icontains=descripcion)

        fecha_desde = self.request.GET.get("fecha_desde")
        fecha_hasta = self.request.GET.get("fecha_hasta")

        if fecha_desde and fecha_hasta:
            qs = qs.filter(fecha__date__range=[fecha_desde, fecha_hasta])
        elif fecha_desde:
            qs = qs.filter(fecha__date__gte=fecha_desde)
        elif fecha_hasta:
            qs = qs.filter(fecha__date__lte=fecha_hasta)

        return qs

class PerfilView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "core.view_perfil"
    login_url = "/login/"
    template_name = "core/perfil.html"
    context_object_name = "ultimas_acciones"  # nombre en el template
    paginate_by = 20  # opcional, si querés paginar en vez de cortar

    def get_queryset(self):
        usuario = self.request.user
        return Auditoria.objects.filter(usuario=usuario).order_by("-fecha")[:100]  # últimas 100 acciones

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["usuario"] = self.request.user
        return context
        
