import os
from llama_cpp import Llama
from django.conf import settings

from .faiss_utils import get_faiss_index
import psutil

import re

def limpiar_respuesta(texto):

    # Eliminar pipes de tablas
    texto = re.sub(r'(\|\s*){2,}', '', texto)

    # Eliminar marcadores del prompt
    texto = re.sub(
        r'\[Final de respuesta\]|\[Final de contexto\]',
        '',
        texto,
        flags=re.IGNORECASE
    )

    # Normalizar espacios
    texto = re.sub(r'\s{2,}', ' ', texto)

    return texto.strip()


def medir_consumo_memoria():
    proceso = psutil.Process(os.getpid())
    memoria_mb = proceso.memory_info().rss / 1024 ** 2
    return round(memoria_mb, 2)

# Ruta al modelo GGUF
LLAMA_MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "modelos_ia",
    "meta-llama-3-8b-instruct.Q4_K_M.gguf"
)

# Variables cache para lazy loading
_modelo_phi = None
_modelo_embeddings = None
_index = None
_fragmentos = None


def get_modelo_phi():
    """Carga el modelo GGUF de Llama solo una vez (lazy loading)."""
    global _modelo_phi
    if _modelo_phi is None:
        try:
            consumo = medir_consumo_memoria()
            print(f"Uso de memoria inicial actual del proceso: {consumo} MB")  
            print("🧠 Cargando modelo GGUF...")
            _modelo_phi = Llama(
                model_path=LLAMA_MODEL_PATH,
                n_ctx=8192,
                n_threads=8,
                n_gpu_layers=0,   # ⚠️ cambia si querés usar GPU
                n_batch=256,
                verbose=False
            )
            print("✅ Modelo GGUF cargado")

            consumo = medir_consumo_memoria()
            print(f"Uso de memoria final actual del proceso: {consumo} MB")
        except Exception as e:
            print(f"⚠️ Error al cargar el modelo GGUF: {e}")
            raise
    return _modelo_phi


def get_indice_faiss():
    """Carga embeddings, índice FAISS y fragmentos una sola vez."""
    global _modelo_embeddings, _index, _fragmentos
    if _index is None:
        print("📦 Cargando índice FAISS en memoria...")
        _modelo_embeddings, _index, _fragmentos = get_faiss_index()
        print(f"✅ Índice FAISS cargado con {len(_fragmentos)} fragmentos")
    return _modelo_embeddings, _index, _fragmentos


def construir_prompt(contexto, pregunta):
    return f"""
Documentos relevantes extraídos de la base de datos:
{contexto}

Instrucciones:
- Responde únicamente con información contenida en los documentos proporcionados.
- No incluyas enlaces externos ni referencias que no provengan de los documentos.
- Si hay datos parciales, armá la mejor respuesta posible con ellos.
- No inventes nada fuera de los documentos.
- No hagas suposiciones.
- No agregues información adicional.
- Responde en texto claro y continuo.
- No incluyas separadores de tablas, símbolos repetidos ni caracteres de formato como |
- Solo si no existe absolutamente ningún dato relacionado, respondé:
"No se encontró información suficiente en los documentos."

Pregunta: {pregunta}
Respuesta:"""

def responder_pregunta_phi2(pregunta, fragmentos_relevantes):
    """
    Genera una respuesta con el modelo usando los fragmentos relevantes.
    - pregunta: texto de la consulta del usuario
    - fragmentos_relevantes: lista de fragmentos de documentos (strings)
    """
    if not fragmentos_relevantes:
        return "No se encontró información relevante en los documentos."

    # 🗂️ Unir fragmentos en un solo contexto
    contexto = "\n".join(fragmentos_relevantes)

    # ✂️ Limitar contexto a 2000 caracteres para no saturar
    LIMITE_CTX = 2000
    if len(contexto) > LIMITE_CTX:
        contexto = contexto[:LIMITE_CTX] + "\n[Texto recortado por límite de contexto]"

    prompt = construir_prompt(contexto, pregunta)

    # 🔎 DEBUG: imprimir qué fragmentos se están pasando
    print("📑 Fragmentos relevantes pasados al modelo:")
    for i, frag in enumerate(fragmentos_relevantes, start=1):
        print(f"{i}. {frag[:200]}...")  # solo los primeros 200 chars

    print("📄 PROMPT ENVIADO AL MODELO ======================")
    print(prompt)
    print("=================================================")

    modelo = get_modelo_phi()

    # 🔹 Máximo de tokens para la respuesta
    max_tokens = 256   # <- límite fijo para evitar cuelgues

    try:
        respuesta = modelo(
            prompt,
            max_tokens=max_tokens,
            stop=["\nPregunta:", "\nRespuesta:"],
            temperature=0.2
        )
        texto = respuesta["choices"][0]["text"].strip()

        # Limpiar ruido de formato (pipes, tablas, etc)
        texto = limpiar_respuesta(texto)

        return texto or "No se encontró información relevante en los documentos."

    except Exception as e:
        print(f"⚠️ Error al generar respuesta: {e}")
        return "Ocurrió un error al procesar la pregunta."
