# documentos/ia/embeddings.py
import os, re, numpy as np, faiss
from pathlib import Path
from functools import lru_cache
from django.conf import settings
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

BASE_DIR = Path(settings.BASE_DIR)
INDEX_PATH = BASE_DIR / "indice_faiss.index"
FRAGMENTOS_PATH = BASE_DIR / "fragmentos_guardados.npy"

@lru_cache(maxsize=1)
def get_modelo_embeddings():
    return SentenceTransformer("intfloat/multilingual-e5-base", device="cpu")

def dividir_en_fragmentos(texto, max_long=350, solapamiento=80, es_normativa=False):
    if es_normativa:
        partes = re.split(r'(Artículo\s+\d+)', texto)
        fragmentos, actual = [], ""
        for i in range(len(partes)):
            if re.match(r'Artículo\s+\d+', partes[i]):
                if actual.strip():
                    fragmentos.append({"texto": actual.strip(), "start": 0, "end": 0})
                actual = partes[i]
            else:
                actual += " " + partes[i]
        if actual.strip():
            fragmentos.append({"texto": actual.strip(), "start": 0, "end": 0})
        return fragmentos

    oraciones = re.split(r'(?<=[.?!])\s+', texto.strip())
    fragmentos, cursor, actual = [], 0, ""
    for o in oraciones:
        if len(actual) + len(o) + 1 <= max_long:
            actual += " " + o
        else:
            ini = max(cursor - len(actual), 0)
            fin = ini + len(actual)
            fragmentos.append({"texto": actual.strip(), "start": ini, "end": fin})
            actual = o
        cursor += len(o) + 1

    if actual:
        ini = max(cursor - len(actual), 0)
        fin = ini + len(actual)
        fragmentos.append({"texto": actual.strip(), "start": ini, "end": fin})

    return fragmentos

def regenerar_indice():
    from documentos.models import Documento
    modelo = get_modelo_embeddings()
    fragmentos, textos = [], []

    for doc in Documento.objects.all():
        texto = (doc.texto_extraido or "").strip()
        if not texto and not doc.asunto and not doc.descripcion:
            continue

        es_normativa = doc.tipo_doc and any(
            kw in doc.tipo_doc.tipo.lower() for kw in ["código", "ley", "norma"]
        )

        if texto:
            frags = dividir_en_fragmentos(texto, es_normativa=es_normativa)
            for f in frags:
                faiss_id = len(textos)
                fragmentos.append({
                    "faiss_id": faiss_id,
                    "texto": f,
                    "doc_id": doc.id,
                    "dep": (
                        doc.dependencia.dependencia_argos.sigla
                        if doc.dependencia and doc.dependencia.dependencia_argos
                        else None
                    ),
                    "leido": doc.leido_por_ia,
                    "asunto": doc.asunto,
                })
                textos.append(f["texto"])

        if doc.asunto:
            faiss_id = len(textos)
            fragmentos.append({
                "faiss_id": faiss_id,
                "texto": {"texto": doc.asunto, "start": 0, "end": 0},
                "doc_id": doc.id,
                "dep": None,
                "leido": doc.leido_por_ia,
                "asunto": doc.asunto,
            })
            textos.append(doc.asunto)

        if doc.descripcion:
            faiss_id = len(textos)
            fragmentos.append({
                "faiss_id": faiss_id,
                "texto": {"texto": doc.descripcion, "start": 0, "end": 0},
                "doc_id": doc.id,
                "dep": None,
                "leido": doc.leido_por_ia,
                "asunto": doc.asunto,
            })
            textos.append(doc.descripcion)

    embeddings = normalize(get_modelo_embeddings().encode(textos))
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(np.array(embeddings, dtype="float32"))

    faiss.write_index(index, str(INDEX_PATH))
    np.save(FRAGMENTOS_PATH, fragmentos, allow_pickle=True)
    print(f"✅ Índice FAISS regenerado con {len(fragmentos)} fragmentos.")

def cargar_indice():
    if not INDEX_PATH.exists() or not FRAGMENTOS_PATH.exists():
        raise FileNotFoundError("❌ No existe el índice. Ejecutá regenerar_indice().")
    index = faiss.read_index(str(INDEX_PATH))
    fragmentos = np.load(FRAGMENTOS_PATH, allow_pickle=True)
    return get_modelo_embeddings(), index, fragmentos
