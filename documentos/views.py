import os
import numpy as np
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse
from .utils import extraer_texto_pdf
from .models import Documento
from .forms import DocumentoForm
from .filters import DocumentoFilter
from .faiss_utils import buscar_fragmentos_relevantes
from .consultas_phi2 import responder_pregunta_phi2, get_faiss_index
from .security import documentos_visibles_para_usuario
from core.auditoria import registrar_auditoria
from collections import defaultdict
from documentos.faiss_utils import agregar_fragmentos_doc
from .faiss_utils import tiene_match



def limitar_por_documento(fragmentos, max_por_doc=1):
    """Devuelve máximo `max_por_doc` fragmentos por documento."""
    agrupados = defaultdict(list)
    for frag in fragmentos:
        agrupados[frag["doc_id"]].append(frag)

    final = []
    for doc_id, frags in agrupados.items():
        frags_ordenados = sorted(frags, key=lambda x: x["score"], reverse=True)
        final.extend(frags_ordenados[:max_por_doc])

    # Ordenar globalmente por score descendente
    return sorted(final, key=lambda x: x["score"], reverse=True)


def rerank_por_coincidencia(fragmentos, query):
    """Sube prioridad a fragmentos que contienen literalmente palabras de la consulta."""
    query_lower = query.lower()
    return sorted(
        fragmentos,
        key=lambda f: (query_lower not in f["texto"].lower(), -f["score"])
    )

def rehidratar_fragmento(doc, start, end, extra=200):
    """
    Devuelve un fragmento más completo a partir de start/end,
    expandiendo hasta terminar la oración.
    """
    texto = doc.texto_extraido or ""
    ini = max(0, start - extra)
    fin = min(len(texto), end + extra)

    # Expandir hasta el próximo punto final
    punto_fin = texto.find('.', fin)
    if punto_fin != -1:
        fin = punto_fin + 1

    return texto[ini:fin].strip()


@login_required
@permission_required("documentos.puede_preguntar_ia", raise_exception=True)
def preguntar_argos(request):
    prompt = request.GET.get("prompt", "").strip()
    if not prompt:
        return JsonResponse({"respuesta": "Ingrese una pregunta."})

    # 🔹 Buscar en FAISS
    fragmentos_relevantes = buscar_fragmentos_relevantes(
        pregunta=prompt,
        top_k=30,
        umbral_alto=0.75,
        umbral_bajo=0.60,
        user=request.user
    )

    if not fragmentos_relevantes:
        return JsonResponse({"respuesta": "No se encontró información relevante."})

    # 🔹 Separar matches y no-matches
    matches = [f for f in fragmentos_relevantes if f.get("match")]
    no_matches = [f for f in fragmentos_relevantes if not f.get("match")]

    # 🔹 Ordenar cada grupo por score descendente
    matches = sorted(matches, key=lambda x: x["score"], reverse=True)
    no_matches = sorted(no_matches, key=lambda x: x["score"], reverse=True)[:5]  # máx 5 extras

    # 🔹 Combinar: primero los matches, luego los demás
    fragmentos_finales = matches + no_matches

    previews, textos_para_modelo = [], []

    for frag in fragmentos_finales:
        try:
            doc = Documento.objects.get(pk=frag["doc_id"])
        except Documento.DoesNotExist:
            continue

        texto_frag = frag["texto"]

        # ⚠️ Excluir asuntos, solo usar texto real
        if texto_frag.strip() != (doc.asunto or "").strip():
            previews.append({
                "doc_id": doc.id,
                "asunto": doc.asunto or "Sin asunto",
                "preview": texto_frag,
                "url": reverse("ver_documento", args=[doc.id]),
                "match": frag.get("match", False),  # ✅ se conserva el match
                "score": frag.get("score", 0)       # opcional: para debug
            })
            textos_para_modelo.append(texto_frag)

    if not textos_para_modelo:
        return JsonResponse({
            "respuesta": "No se encontró información suficiente en los documentos.",
            "fragmentos": previews
        })

    # 🔹 Generar respuesta con los fragmentos seleccionados
    respuesta = responder_pregunta_phi2(prompt, textos_para_modelo)

    return JsonResponse({
        "respuesta": respuesta,
        "fragmentos": previews,
    })

@login_required
@permission_required("documentos.puede_preguntar_ia", raise_exception=True)
def preguntar_argos_html(request):
    if request.method == "GET" and request.GET.get("pregunta"):
        # Reutilizar la lógica JSON de preguntar_argos
        request.GET = request.GET.copy()
        request.GET["prompt"] = request.GET.get("pregunta")
        return preguntar_argos(request) 

    # Renderizar el template para consultas normales
    return render(request, "documentos/preguntar_argos.html")


@login_required
def buscar_con_faiss(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"error": "Falta la consulta."})

    modelo_embeddings, index, fragmentos = get_faiss_index()
    vec = modelo_embeddings.encode([query])
    distancias, indices = index.search(np.array(vec, dtype="float32"), 10)

    resultados = []
    for j, i in enumerate(indices[0]):
        if i >= len(fragmentos):  # seguridad por si hay índice inválido
            continue

        frag = fragmentos[i]
        # Extraer el texto (puede estar en dict o en string según cómo se guardó)
        texto = frag["texto"]["texto"] if isinstance(frag.get("texto"), dict) else str(frag.get("texto"))

        distancia = float(distancias[0][j])
        contiene = query.lower() in texto.lower()
        resultados.append({
            "doc_id": frag.get("doc_id"),
            "asunto": frag.get("asunto", "Sin asunto"),
            "texto": texto[:300],  # preview de 300 chars
            "distancia": distancia,
            "match": contiene,
        })

    # Ordenar: primero los que contienen literalmente el query, luego por similitud
    resultados.sort(key=lambda x: (not x["match"], x["distancia"]))

    

    return JsonResponse({
        "consulta": query,
        "resultados": resultados[:10],
    })

# -- Vistas CRUD para Documentos --
class CrearDocumentoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'documentos.add_documento'
    login_url = '/login'
    template_name = "documentos/crear.html"

    def get(self, request, *args, **kwargs):
        form = DocumentoForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.creada_por = request.user

            post.save()

            # Extraer texto del PDF
            if post.informe and not post.texto_extraido:
                ruta = post.informe.path
                if os.path.exists(ruta):
                    texto = extraer_texto_pdf(ruta)
                    if texto:
                        post.texto_extraido = texto.strip()
                        post.save(update_fields=["texto_extraido"])

            # ✅ Indexar en FAISS inmediatamente
            try:
                agregar_fragmentos_doc(post.id)
                print(f"✅ Documento {post.id} indexado en FAISS")
            except Exception as e:
                print(f"⚠️ Error al indexar en FAISS: {e}")

            form.instance = post
            form.save_m2m()

            messages.success(request, "Documento agregado correctamente.")
            registrar_auditoria(
                request, "CREATE", "Documento", objeto_id=str(post.pk),
                descripcion=f"Se creó documento '{post.asunto}'"
            )
            return redirect("documentos")



class EditarDocumentoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'documentos.change_documento'
    login_url = '/login'
    template_name = "documentos/editar.html"

    def get(self, request, id, *args, **kwargs):
        documento = get_object_or_404(Documento, id=id)
        form = DocumentoForm(instance=documento)
        return render(request, self.template_name, {"form": form, "documento": documento})

    def post(self, request, id, *args, **kwargs):
        documento = get_object_or_404(Documento, id=id)
        form = DocumentoForm(request.POST, request.FILES, instance=documento)
        if form.is_valid():
            post = form.save(commit=False)

            post.save()

            if "informe" in request.FILES:
                ruta = post.informe.path
                if os.path.exists(ruta):
                    texto = extraer_texto_pdf(ruta)
                    if texto:
                        post.texto_extraido = texto.strip()
                        post.save(update_fields=["texto_extraido"])

            form.instance = post
            form.save_m2m()

            registrar_auditoria(
                request, "UPDATE", "Documento", objeto_id=str(documento.pk),
                descripcion=f"Edición del documento '{documento.asunto}'"
            )
            messages.success(request, "Documento actualizado correctamente.")

        return render(request, self.template_name, {"form": form, "documento": documento})


class EliminarDocumentoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'documentos.delete_documento'
    login_url = '/login'

    def post(self, request, id, *args, **kwargs):
        documento = get_object_or_404(Documento, id=id)

        # 🔹 Primero borrar del índice FAISS
        from documentos.faiss_utils import eliminar_fragmentos_por_doc
        eliminar_fragmentos_por_doc(documento.id)

        # 🔹 Registrar auditoría y borrar de la BD
        registrar_auditoria(
            request, "DELETE", "Documento", objeto_id=str(documento.pk),
            descripcion=f"Se eliminó el documento '{documento.asunto}'"
        )
        documento.delete()

        messages.success(request, f"Documento '{documento.asunto}' eliminado correctamente.")
        return redirect("documentos")


class VerDocumentoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'documentos.view_documento'
    login_url = '/login'
    template_name = "documentos/ver.html"

    def get(self, request, id, *args, **kwargs):
        documento = get_object_or_404(Documento, id=id)
        registrar_auditoria(
            request, "VIEW", "Documento", objeto_id=str(documento.pk),
            descripcion=f"Visualización del documento '{documento.asunto}'"
        )
        return render(request, self.template_name, {"documento": documento})


class DocumentosListView(LoginRequiredMixin, PermissionRequiredMixin, View):
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
