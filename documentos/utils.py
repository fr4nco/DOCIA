import os
import platform
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps, ImageStat
import pytesseract
import io

# Configurar Tesseract en Windows
if platform.system() == "Windows":
    posible_ruta = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(posible_ruta):
        pytesseract.pytesseract.tesseract_cmd = posible_ruta
    else:
        print("⚠️ Tesseract no encontrado en la ruta esperada. Verificá la instalación.")

def preprocesar_imagen_para_ocr(imagen):
    imagen = imagen.resize((imagen.width * 2, imagen.height * 2))
    imagen = ImageOps.grayscale(imagen)

    stat = ImageStat.Stat(imagen)
    media_brillo = stat.mean[0]

    if media_brillo < 127:
        imagen = ImageOps.invert(imagen)

    imagen = ImageEnhance.Contrast(imagen).enhance(2.0)
    imagen = imagen.point(lambda x: 0 if x < 110 else 255, '1')

    return imagen

def extraer_texto_pdf(ruta_pdf):
    texto_total = ""

    try:
        with fitz.open(ruta_pdf) as doc:
            for i, pagina in enumerate(doc):
                texto = pagina.get_text()
                if texto.strip():
                    print(f"[Página {i+1}] Texto embebido detectado.")
                    texto_total += texto + "\n"
                else:
                    print(f"[Página {i+1}] Sin texto embebido. Aplicando OCR...")
                    try:
                        pix = pagina.get_pixmap(dpi=300)
                        imagen_bytes = pix.tobytes("png")
                        imagen = Image.open(io.BytesIO(imagen_bytes))
                        imagen = preprocesar_imagen_para_ocr(imagen)

                        texto_ocr = pytesseract.image_to_string(imagen, lang="spa+eng+por")
                        print(f"[Página {i+1}] OCR OK. Texto: {texto_ocr[:100]!r}")
                        texto_total += texto_ocr + "\n"
                    except Exception as e:
                        print(f"[Página {i+1}] Error en OCR: {e}")

        return texto_total.strip().replace("\n", " ").replace("  ", " ")

    except Exception as e:
        print(f"❌ Error general al procesar PDF: {e}")
        return ""
