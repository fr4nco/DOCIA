# DOCIA

DOCIA es una aplicación web para **análisis y consulta inteligente de documentos**  
orientada a entornos cerrados, con foco en **trazabilidad, seguridad y fidelidad de respuesta**.

Este proyecto implementa un flujo de *Recuperación Aumentada por Generación (RAG)* usando:
- extracción de texto desde PDFs,
- indexación semántica con FAISS,
- recuperación de fragmentos relevantes,
- generación de respuestas con modelos de lenguaje locales (LLMs),
- y limpieza/control de salida para evitar alucinaciones.

---

## 🧩 ¿Qué problema resuelve?

Cuando se trabaja con documentos extensos o sensibles, las personas necesitan:
- encontrar información relevante
- obtener respuestas en lenguaje natural
- sin exponer datos a servicios externos
- manteniendo trazabilidad y control

DOCIA permite esto sin depender de la nube.

---

## 🚀 Arquitectura general

1. **Carga de documento PDF**
2. **Extracción de texto**
3. **Indexación semántica** (FAISS)
4. **Recuperación de contexto relevante**
5. **Generación de respuestas con LLM local**
6. **Post-procesado y limpieza de salida**

---

## 🛠️ Tecnologías usadas

- Python
- Django
- PostgreSQL
- FAISS
- Modelos de lenguaje locales (GGUF, LLaMA, Mistral, etc.)
- Frontend básico con templates Django

> *Modelos no incluidos*

---

## 📦 Estructura del proyecto

DOCIA/
├── docia/
├── core/
├── documentos/
├── media/               
├── modelos_ia/          
├── static/
├── templates/
├── manage.py
