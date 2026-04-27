# PDFimpresistem

Plataforma web para la gestión y manipulación de documentos PDF, desarrollada por **[Impresistem S.A.S](https://www.impresistem.com)**.

---

## Descripción general

PDFimpresistem es una aplicación web construida con **Flask** que ofrece más de 25 herramientas para procesar archivos PDF. La aplicación se estructura en cinco niveles de complejidad — básico, intermedio, avanzado e interactivo — permitiendo tanto operaciones simples como procesos sofisticados como OCR y conversión a PDF/A. Todo funciona directamente desde el navegador sin necesidad de instalar software adicional.

---

## Stack tecnológico

### Backend
| Componente | Tecnología | Versión | Propósito |
|---|---|---|---|
| Framework | Flask | 2.3.3 | Servidor web y routing |
| Templates | Jinja2 | 3.1.2 | Renderizado de vistas |
| WSGI | Werkzeug | 2.3.7 | Servidor de producción |
| Scheduler | APScheduler | 3.10.4 | Limpieza automática programada |
| Zona horaria | pytz | — | Hora Colombia (America/Bogota) |

### Librerías PDF
| Librería | Versión | Función |
|---|---|---|
| **PyMuPDF** | 1.24.13 | Motor principal de manipulación PDF |
| **pdfplumber** | 0.11.4 | Extracción de tablas a Excel |
| **pdf2docx** | 0.5.8 | Conversión a Word |
| **pikepdf** | 9.2.0 | Conversión a PDF/A |
| **python-docx** | 1.1.2 | Generación de documentos Word |

### OCR y procesamiento de imágenes
| Librería | Función |
|---|---|
| **pytesseract** | Reconocimiento óptico de caracteres |
| **Pillow** | Procesamiento de imágenes |
| **openpyxl** | Generación de archivos Excel |
| **numpy** | Operaciones numéricas |
| **lxml** | Procesamiento XML |

### Frontend
- **Tailwind CSS 2.2.16** — Estilos (CDN)
- **Fabric.js** — Canvas interactivo (firma, edición)
- **Sortable.js** — Drag-and-drop (ordenar páginas)
- **pdf-lib** — Manipulación de PDFs en el cliente
- **pdf.js** — Renderizado de PDFs en el navegador
- **JSZip + pptxgenjs** — Generación de PowerPoint en cliente
- **difflib** (Python) — Comparación de documentos

---

## Estructura del proyecto

```
PDFimpresistem/
├── app.py                 # Punto de entrada, blueprints, scheduler
├── config.py              # Rutas de uploads/outputs
├── utils.py               # Helpers: parsear_paginas, limpiar_carpeta, hex_a_rgb
├── requirements.txt      # Dependencias Python
├── app.wsgi               # Configuración para deployment WSGI
├── routes/
│   ├── __init__.py
│   ├── main.py            # Rutas UI: reorder_ui, crop_ui, edit_ui, etc.
│   ├── basic.py           # Herramientas básicas: rotate, extract, watermark, protect, unlock, flatten
│   ├── intermediate.py    # Herramientas intermedias: reorder, organize, crop, compress, page_numbers, repair, pdf_to_pdfa, images
│   ├── advanced.py        # Herramientas avanzadas: sign, pdf_to_excel, edit, censor, ocr, compare, form_filler
│   └── api.py            # Endpoints API: thumbnails, compare, ocr stream, page preview, signatures
├── templates/
│   ├── index.html         # Página principal con 25+ herramientas
│   ├── reorder.html       # Interfaz drag-and-drop para reordenar páginas
│   ├── organize.html      # Grid de páginas para eliminar
│   ├── crop.html          # Editor visual de márgenes
│   ├── edit.html          # Editor de texto en canvas
│   ├── sign.html          # Firma arrastrable con Fabric.js
│   ├── censor.html        # Censura visual de zonas
│   ├── form_filler.html   # Split-view para rellenar formularios
│   ├── compare.html       # Comparación inline de dos PDFs
│   └── ocr.html           # Interfaz OCR con streaming SSE
├── uploads/               # Archivos temporales subidos por usuarios
├── outputs/               # Archivos generados para descarga
└── RESUMEN_CAMBIOS.md     # Historial de funcionalidades implementadas
```

---

## Todas las herramientas

### Nivel Básico (`routes/basic.py`)

| Herramienta | Ruta | Descripción |
|---|---|---|
| Rotar PDF | `POST /rotate` | Rota todas las páginas en 90°, 180° o 270° |
| Extraer páginas | `POST /extract` | Extrae páginas específicas (ej: `1,3-5,8`) |
| Marca de agua | `POST /watermark` | Texto semitransparente en diagonal |
| Proteger PDF | `POST /protect` | Encripta con AES-256 y contraseña |
| Desbloquear PDF | `POST /unlock` | Elimina la protección por contraseña |
| Aplanar PDF | `POST /flatten` | Convierte formularios y anotaciones en contenido estático |

### Nivel Intermedio (`routes/intermediate.py`)

| Herramienta | Ruta | Descripción |
|---|---|---|
| Reordenar PDF | `POST /reorder` | Reorganiza páginas (todas deben estar una vez) |
| Organizar PDF | `POST /organize` | Elimina páginas específicas |
| Números de página | `POST /page_numbers` | Inserta "Página X de Y" en pie de página |
| Comprimir PDF | `POST /compress` | Optimiza estructura interna, calcula ahorro % |
| PDF a JPG/PNG | `POST /pdf_to_jpg` | Convierte páginas a imágenes ZIP (72/150/300 DPI) |
| JPG a PDF | `POST /jpg_to_pdf` | Convierte imágenes a PDF con tamaño exacto |
| Reparar PDF | `POST /repair` | Intenta recuperar documentos dañados |
| Recortar PDF | `POST /crop` | Recorta márgenes por porcentaje (0-40% por lado) |
| PDF a PDF/A | `POST /pdf_to_pdfa` | Convierte al estándar ISO 19005-2 (archivo digital) |

### Nivel Avanzado (`routes/advanced.py`)

| Herramienta | Ruta | Descripción |
|---|---|---|
| PDF a Word | `POST /convert` | Convierte a .docx preservando formato |
| Firmar PDF | `POST /sign` | Inserta imagen de firma en página específica |
| PDF a Excel | `POST /pdf_to_excel` | Extrae tablas a hojas separadas |
| Editar PDF | `POST /edit` | Agrega texto en posición específica |
| Censurar PDF | `POST /censor` | Dibuja rectángulos opacos sobre zonas sensibles |
| OCR PDF | `POST /ocr` | Hace buscable un PDF escaneado (requiere Tesseract) |
| Comparar PDF | `POST /compare` | Genera reporte HTML con diferencias |
| Rellenar formularios | `POST /form_filler` | Detecta y llena campos interactivos de un PDF |

### Módulos Interactivos (UI)

| Módulo | Ruta UI | Tecnología |
|---|---|---|
| Ordenar PDF | `/reorder_ui` | Sortable.js + miniaturas |
| Organizar PDF | `/organize_ui` | Grid de selección |
| Recortar PDF | `/crop_ui` | Overlay de márgenes con Fabric.js |
| Editar PDF | `/edit_ui` | Canvas con herramientas de texto |
| Firmar PDF | `/sign_ui` | Canvas Fabric.js con firma arrastrable |
| Censurar PDF | `/censor_ui` | Editor visual de zonas |
| Rellenar formularios | `/form_filler` | Split-view con highlights |
| Comparar PDF | `/compare_ui` | Difftable HTML |
| OCR PDF | `/ocr_ui` | Streaming SSE con progress |

### Endpoints API (`routes/api.py`)

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/page_preview` | POST | Genera preview de una página |
| `/api/thumbnails` | POST | Genera miniaturas de todas las páginas |
| `/api/save_signature` | POST | Guarda imagen de firma dibujada |
| `/api/page_preview_by_name` | POST | Preview por nombre de archivo |
| `/api/compare` | POST | Compara dos PDFs (retorna JSON) |
| `/api/ocr/upload` | POST | Prepara PDF para OCR |
| `/api/ocr/stream` | GET | Stream SSE con progreso del OCR |

---

## Dependencias externas del sistema

### Ubuntu / Linux
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-spa
```
Necesario para la herramienta OCR (`/ocr`).

---

## Limpieza automática

Un scheduler de APScheduler ejecuta `limpiar_archivos_programada()` todos los días a las **7:00 PM hora Colombia**, eliminando todos los archivos de `/uploads` y `/outputs`. El usuario también puede activar la limpieza manual desde el botón **"Limpiar archivos"** en el header.

---

## Deployment

### Desarrollo
```python
# Descomentar en app.py
app.run(host='0.0.0.0', port=8080, debug=True)
```

### Producción (mod_wsgi)
El archivo `app.wsgi` permite desplegar con Apache + mod_wsgi. La variable `application` está definida en `app.py` como alias de `app`.

---

## Configuración de carpetas

Definida en `config.py`:
- `UPLOAD_FOLDER` → `./uploads/` (archivos temporales)
- `OUTPUT_FOLDER` → `./outputs/` (resultados para descarga)

Ambas se crean automáticamente si no existen.

---

## Formato de paginas

Todas las herramientas que aceptan rangos de páginas (`extract`, `reorder`, `organize`) usan la misma función `parsear_paginas()`:

```
1,3,5         → páginas individuales
2-6           → rango
1,3-5,8       → combinación
```

Retorna índices base 0. Las páginas fuera de rango se filtran silenciosamente.

---

## Conversión a PDF/A

Se usa **pikepdf** para insertar metadatos XMP que declaran cumplimiento PDF/A-2B (ISO 19005-2). Este formato es obligatorio en trámites gubernamentales en Colombia.

---

## OCR

Convierte cada página del PDF escaneado en imagen a 300 DPI, aplica Tesseract OCR (español), e inserta el texto extraído de forma invisible (`fontsize=0`, `color=white`) en un nuevo PDF. El resultado mantiene la apariencia visual pero tiene texto buscable y copiable.

---

## Licencia

Propiedad de **Impresistem S.A.S.** — Todos los derechos reservados.