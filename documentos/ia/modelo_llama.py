# documentos/ia/modelo_llama.py
import os
from pathlib import Path
from django.conf import settings
from llama_cpp import Llama

LLAMA_MODEL_PATH = Path(settings.BASE_DIR) / "modelos_ia" / "capybarahermes-2.5-mistral-7b.Q4_K_M.gguf"
_model = None

def get_llama():
    global _model
    if _model is None:
        print("🧠 Cargando modelo GGUF...")
        _model = Llama(
            model_path=str(LLAMA_MODEL_PATH),
            n_ctx=8192,
            n_threads=8,
            n_gpu_layers=0,
            n_batch=256,
            verbose=False
        )
        print("✅ Modelo cargado")
    return _model

def construir_prompt(contexto, pregunta):
    return f"""
Documentos relevantes extraídos de la base de datos:
{contexto}

Instrucciones:
Respondé de forma concisa y basada *exclusivamente* en los documentos anteriores.
Si no hay información suficiente, respondé con:
"No se encontró información relevante en los documentos."

Pregunta: {pregunta}
Respuesta:"""

def responder(pregunta, fragmentos, max_tokens=128):
    if not fragmentos:
        return "No se encontró información relevante."
    contexto = "\n".join(fragmentos)
    if len(contexto) > 2000:
        contexto = contexto[:2000] + "..."
    prompt = construir_prompt(contexto, pregunta)

    try:
        out = get_llama()(prompt, max_tokens=max_tokens, temperature=0.2)
        texto = out["choices"][0]["text"].strip()
        return texto.split("\n")[0].strip() or "No se encontró información relevante."
    except Exception as e:
        print(f"⚠️ Error modelo: {e}")
        return "Error al generar la respuesta."
