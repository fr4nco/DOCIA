import os
import re
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from django.conf import settings
from functools import lru_cache
from sklearn.preprocessing import normalize   # 🔹 FIX: para coseno

# 📦 Rutas de archivos
INDEX_PATH = os.path.join(settings.BASE_DIR, "indice_faiss.index")
FRAGMENTOS_PATH = os.path.join(settings.BASE_DIR, "fragmentos_guardados.npy")



def dividir_en_fragmentos(texto, max_long=1200, solapamiento=200, es_normativa=False):
    """
    Divide un texto en fragmentos para indexar.
    Si es normativa, separa por artículos.
    """
    if es_normativa:
        partes = re.split(r'(Artículo\s+\d+)', texto)
        fragmentos, actual = [], ""
        for i in range(len(partes)):
            if re.match(r'Artículo\s+\d+', partes[i]):
                if actual.strip():
                    fragmentos.append({"texto": actual.strip()})
                actual = partes[i]
            else:
                actual += " " + partes[i]
        if actual.strip():
            fragmentos.append({"texto": actual.strip()})
        return fragmentos

    oraciones = re.split(r'(?<=[.?!])\s+', texto.strip())
    fragmentos, actual = [], ""
    for o in oraciones:
        if len(actual) + len(o) + 1 <= max_long:
            actual += " " + o
        else:
            fragmentos.append({"texto": actual.strip()})
            actual = o
    if actual:
        fragmentos.append({"texto": actual.strip()})
    return fragmentos




# 📦 Rutas de archivos
INDEX_PATH = os.path.join(settings.BASE_DIR, "indice_faiss.index")
FRAGMENTOS_PATH = os.path.join(settings.BASE_DIR, "fragmentos_guardados.npy")

...
def regenerar_indice_faiss():
    from documentos.models import Documento
    modelo_embeddings = SentenceTransformer("intfloat/multilingual-e5-base", device="cpu")

    fragmentos, textos = [], []

    for doc in Documento.objects.all():
        texto = (doc.texto_extraido or "").strip()
        if not texto:
            continue

        es_normativa = doc.tipo_doc and any(
            kw in doc.tipo_doc.tipo.lower() for kw in ["código", "ley", "norma"]
        )

        fragmentos_doc = dividir_en_fragmentos(texto, es_normativa=es_normativa)
        for frag in fragmentos_doc:
            faiss_id = len(textos)
            frag_original = frag["texto"]
            frag_norm = normalizar_texto(frag_original)

            fragmentos.append({
                "faiss_id": faiss_id,
                "texto": frag_original,          # 🔹 original para mostrar
                "texto_norm": frag_norm,         # 🔹 normalizado para embeddings
                "doc_id": doc.id,
                "dep": (
                    doc.dependencia.dependencia_argos.sigla
                    if doc.dependencia and doc.dependencia.dependencia_argos
                    else None
                ),
                "leido": doc.leido_por_ia,
                "asunto": doc.asunto,
            })

            print(f"Total fragmentos generados: {len(fragmentos)}")

            textos.append(frag_norm)  # 🔹 solo normalizado para embeddings

    embeddings = modelo_embeddings.encode(textos)
    embeddings = normalize(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])  # producto interno ≈ coseno
    if len(embeddings) > 0:
        index.add(np.array(embeddings, dtype="float32"))

    faiss.write_index(index, INDEX_PATH)
    np.save(FRAGMENTOS_PATH, fragmentos, allow_pickle=True)

    get_faiss_index.cache_clear()
    print(f"✅ Índice FAISS regenerado con {len(fragmentos)} fragmentos.")


import re
import unicodedata

# 🔹 Función para normalizar texto
def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""

    # 🔹 Minúsculas y quitar tildes
    texto = texto.lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

    # 🔹 Quitar separadores en números (puntos, guiones, espacios)
    texto = re.sub(r'(?<=\d)[\.\-\s](?=\d)', '', texto)

    # 🔹 Matrículas: ca-1234-ax / ca 1234 ax → ca1234ax
    texto = re.sub(
        r'\b([a-z]{1,3})[\s\-]?(\d{3,4})(?:[\s\-]?([a-z]{1,3}))?\b',
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3) or ''}",
        texto
    )

    # 🔹 SGSP: números largos (7-10 dígitos) → dejamos solo número
    # Antes: sgspXXXXXXXX → ahora: XXXXXXXX
    # Si querés mantener prefijo, cambialo a r"sgsp\1"
    texto = re.sub(r'\b(\d{7,10})\b', r"\1", texto)

    # 🔹 Teléfonos: 2-3 + 3 + 3/4 dígitos → solo números
    texto = re.sub(r'\b(\d{2,3})(\d{3})(\d{3,4})\b', r"\1\2\3", texto)

    # 🔹 CI uruguaya: 3.456.789-2 → 34567892
    texto = re.sub(r'\b(\d{1,2})(\d{3})(\d{3})(\d)\b', r"\1\2\3\4", texto)

    # 🔹 Colapsar espacios múltiples
    texto = re.sub(r'\s+', ' ', texto)

    return texto.strip()
PATRONES = {
    # SGSP: 7–10 dígitos seguidos
    "sgsp": r"\b\d{7,10}\b",

    # Matrículas: letras + 3-4 números + opcionales letras
    "matricula": r"\b[a-z]{1,3}\d{3,4}[a-z]{0,3}\b",

    # Teléfonos: 8–12 dígitos (después de normalizar)
    "telefono": r"\b\d{8,12}\b",

    # CI uruguaya: exactamente 8 dígitos (después de normalizar)
    "ci": r"\b\d{8}\b",

    # Direcciones (se mantienen igual)
    "direccion": r"\b(calle|av|avenida|ruta|camino)\s+\w+",
}


def tiene_match(query: str, texto: str) -> bool:
    return normalizar_texto(query) in normalizar_texto(texto)

# 🔹 Función de coincidencias clave (boost extra)
def coincidencias_clave(pregunta: str, fragmentos: list):
    resultados_extra = []
    texto_preg = normalizar_texto(pregunta)

    for tipo, patron in PATRONES.items():
        matches = re.findall(patron, texto_preg)
        if not matches:
            continue

        for frag in fragmentos:
            frag_txt = normalizar_texto(frag["texto"])
            if any(m.lower() in frag_txt for m in matches):
                frag_boost = frag.copy()
                # Aumentamos el score → aparecen más arriba
                frag_boost["score"] = frag_boost.get("score", 0) + 3.0
                resultados_extra.append(frag_boost)

    return resultados_extra

def buscar_fragmentos_relevantes(
    pregunta: str,
    *,
    top_k: int = 20,
    umbral_alto: float = 0.70,
    umbral_bajo: float = 0.45,   # 🔹 lo bajo un poco para casos débiles
    user=None
):
    """
    Busca fragmentos relevantes en FAISS con soporte para permisos por usuario.
    Usa texto normalizado para embeddings y comparaciones.
    """
    modelo_embeddings, index, fragmentos = get_faiss_index()

    # 🔹 Normalizar la query
    pregunta_norm = normalizar_texto(pregunta)
    vec_pregunta = modelo_embeddings.encode([pregunta_norm])
    vec_pregunta = normalize(vec_pregunta)
    distancias, indices = index.search(np.array(vec_pregunta, dtype="float32"), top_k)

    fragmentos_filtrados = []

    # Dependencia del usuario (si tiene)
    user_dep_sigla = (
        user.dependencia.dependencia_argos.sigla
        if user and getattr(user, "dependencia", None)
        and getattr(user.dependencia, "dependencia_argos", None)
        else None
    )

    # --- Paso 1: similitud alta ---
    for idx, i in enumerate(indices[0]):
        score = float(distancias[0][idx])
        if score <= -1e+20:
            continue
        if i >= len(fragmentos):
            continue
        if score < umbral_alto:
            continue

        frag = fragmentos[i]
        frag_dict = {
            "faiss_id": i,
            "texto": frag.get("texto"),
            "doc_id": frag.get("doc_id"),
            "dep": frag.get("dep"),
            "leido": frag.get("leido"),
            "asunto": frag.get("asunto"),
            "score": score,
            "match": tiene_match(pregunta, frag.get("texto", ""))  # ✅
        }

        if user and user.groups.filter(name="argos_consultas_general").exists():
            fragmentos_filtrados.append(frag_dict)
        else:
            if frag_dict.get("leido") and (frag_dict.get("dep") == user_dep_sigla or frag_dict.get("dep") is None):
                fragmentos_filtrados.append(frag_dict)

    # --- Paso 2: similitud baja ---
    if not fragmentos_filtrados:
        for idx, i in enumerate(indices[0]):
            score = float(distancias[0][idx])
            if score <= -1e+20:
                continue
            if i >= len(fragmentos):
                continue
            if score < umbral_bajo:
                continue

            frag = fragmentos[i]
            frag_dict = {
                "faiss_id": i,
                "texto": frag.get("texto"),
                "doc_id": frag.get("doc_id"),
                "dep": frag.get("dep"),
                "leido": frag.get("leido"),
                "asunto": frag.get("asunto"),
                "score": score,
                "match": tiene_match(pregunta, frag.get("texto", ""))  # ✅
            }
            fragmentos_filtrados.append(frag_dict)

    # --- Paso 3: coincidencia exacta con nombres propios ---
    palabras = pregunta.split()
    if len(palabras) >= 2:
        nombre_query = normalizar_texto(" ".join(palabras))
        for frag in fragmentos:
            if nombre_query in frag.get("texto_norm", ""):
                fragmentos_filtrados.append({
                    "faiss_id": frag.get("faiss_id"),
                    "texto": frag.get("texto"),
                    "doc_id": frag.get("doc_id"),
                    "dep": frag.get("dep"),
                    "leido": frag.get("leido"),
                    "asunto": frag.get("asunto"),
                    "score": 5.0,
                    "match": tiene_match(pregunta, frag.get("texto", ""))  # ✅
                })

    # --- Paso 4: fallback con keywords ---
    if len(fragmentos_filtrados) < 3:
        for frag in fragmentos:
            texto_norm = frag.get("texto_norm", "")
            if any(normalizar_texto(pal) in texto_norm for pal in palabras):
                fragmentos_filtrados.append({
                    "faiss_id": frag.get("faiss_id"),
                    "texto": frag.get("texto"),
                    "doc_id": frag.get("doc_id"),
                    "dep": frag.get("dep"),
                    "leido": frag.get("leido"),
                    "asunto": frag.get("asunto"),
                    "score": 2.0,
                    "match": tiene_match(pregunta, frag.get("texto", ""))  # ✅
                })

    # --- Paso 5: coincidencias clave (SGSP, matrícula, direcciones) ---
    extras = coincidencias_clave(pregunta, fragmentos)
    for frag_boost in extras:
        frag_boost["match"] = tiene_match(pregunta, frag_boost.get("texto", ""))  # ✅
        fragmentos_filtrados.append(frag_boost)

    # --- Fallback explícito si no hay nada ---
    if not fragmentos_filtrados:
        return [{
            "texto": "⚠️ No se encontró información suficiente en los documentos.",
            "score": 0,
            "match": False
        }]

    # --- 🔹 Deduplicado final por (doc_id, texto) ---
    vistos, limpios = set(), []
    for f in fragmentos_filtrados:
        clave = (f.get("doc_id"), f.get("texto"))
        if clave not in vistos:
            limpios.append(f)
            vistos.add(clave)

    # --- Orden final ---
    limpios = sorted(limpios, key=lambda x: x["score"], reverse=True)
    return limpios


@lru_cache(maxsize=1)
def get_faiss_index():
    print("⏳ Cargando embeddings y FAISS...")
    modelo_embeddings = SentenceTransformer("intfloat/multilingual-e5-base", device="cpu")

    if not os.path.exists(INDEX_PATH) or not os.path.exists(FRAGMENTOS_PATH):
        raise FileNotFoundError("❌ No existe índice FAISS. Ejecutá regenerar_indice_faiss().")

    index = faiss.read_index(INDEX_PATH)
    fragmentos = np.load(FRAGMENTOS_PATH, allow_pickle=True)
    print(f"✅ FAISS cargado con {len(fragmentos)} fragmentos.")
    return modelo_embeddings, index, fragmentos


def agregar_fragmentos_doc(doc_id):
    from documentos.models import Documento

    modelo_embeddings, index, fragmentos = get_faiss_index()
    fragmentos = list(fragmentos)

    doc = Documento.objects.filter(id=doc_id).first()
    if not doc or not doc.texto_extraido:
        print(f"⚠️ Documento {doc_id} no tiene texto extraído.")
        return

    fragmentos_doc = dividir_en_fragmentos(doc.texto_extraido)
    textos = [normalizar_texto(f["texto"]) for f in fragmentos_doc]  # 🔹 normalizados
    embeddings = modelo_embeddings.encode(textos)
    embeddings = normalize(embeddings)

    base_id = len(fragmentos)
    for idx, frag in enumerate(fragmentos_doc):
        frag_original = frag["texto"]
        frag_norm = normalizar_texto(frag_original)

        fragmentos.append({
            "faiss_id": base_id + idx,
            "texto": frag_original,      # 🔹 original
            "texto_norm": frag_norm,     # 🔹 normalizado
            "doc_id": doc.id,
            "dep": (
                doc.dependencia.dependencia_argos.sigla
                if doc.dependencia and doc.dependencia.dependencia_argos
                else None
            ),
            "leido": doc.leido_por_ia,
            "asunto": getattr(doc, "asunto", None),
        })

    index.add(np.array(embeddings, dtype="float32"))

    faiss.write_index(index, INDEX_PATH)
    np.save(FRAGMENTOS_PATH, fragmentos, allow_pickle=True)
    get_faiss_index.cache_clear()

    print(f"✅ Documento {doc_id} agregado al índice con {len(fragmentos_doc)} fragmentos.")



def eliminar_fragmentos_por_doc(doc_id):
    modelo_embeddings, index, fragmentos = get_faiss_index()
    fragmentos = list(fragmentos)

    frag_indices = [i for i, f in enumerate(fragmentos) if f.get("doc_id") == doc_id]
    if not frag_indices:
        print(f"⚠️ Documento {doc_id} no tenía fragmentos en el índice.")
        return

    print(f"🗑️ Eliminando {len(frag_indices)} fragmentos del documento {doc_id}...")

    fragmentos_restantes = [f for f in fragmentos if f.get("doc_id") != doc_id]
    textos = [f["texto"] for f in fragmentos_restantes]

    embeddings = modelo_embeddings.encode(textos)
    embeddings = normalize(embeddings)

    nuevo_index = faiss.IndexFlatIP(embeddings.shape[1])
    if len(embeddings) > 0:
        nuevo_index.add(np.array(embeddings, dtype="float32"))

    for i, f in enumerate(fragmentos_restantes):
        f["faiss_id"] = i

    faiss.write_index(nuevo_index, INDEX_PATH)
    np.save(FRAGMENTOS_PATH, fragmentos_restantes, allow_pickle=True)
    get_faiss_index.cache_clear()

    print(f"✅ Documento {doc_id} eliminado. Total fragmentos ahora: {len(fragmentos_restantes)}")
