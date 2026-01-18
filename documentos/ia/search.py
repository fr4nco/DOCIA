# documentos/ia/search.py
import numpy as np
from .embeddings import cargar_indice, get_modelo_embeddings
from sklearn.preprocessing import normalize

def buscar_fragmentos(pregunta, top_k=30, umbral=0.60, user=None):
    modelo, index, fragmentos = cargar_indice()
    vec = normalize(modelo.encode([pregunta]))
    distancias, indices = index.search(np.array(vec, dtype="float32"), top_k)

    resultados = []
    for idx, i in enumerate(indices[0]):
        if i >= len(fragmentos): continue
        frag = fragmentos[i]
        score = float(distancias[0][idx])
        if score < umbral: continue
        texto = frag["texto"]["texto"] if isinstance(frag["texto"], dict) else str(frag["texto"])
        resultados.append({
            "doc_id": frag.get("doc_id"),
            "texto": texto,
            "asunto": frag.get("asunto"),
            "score": score
        })
    return sorted(resultados, key=lambda x: x["score"], reverse=True)
