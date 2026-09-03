# routes/main.py — Blueprint: main

from flask import Blueprint, request, render_template, send_from_directory, redirect, url_for, session
from utils import limpiar_carpeta, eliminar_motw
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from werkzeug.utils import secure_filename
import fitz
from pdf2docx import Converter
from pptx import Presentation
from pptx.util import Inches
import os
import re
import subprocess
import io

main_bp = Blueprint('main', __name__)


# ─── Ruta para servir el logo ─────────────────────────────────────────────
@main_bp.route('/logos/<path:filename>')
def serve_logo(filename):
    """Sirve imágenes de la raíz del proyecto."""
    from config import BASE_DIR
    return send_from_directory(BASE_DIR, filename)


# ─── Cierre de sesión ─────────────────────────────────────────────────────
@main_bp.route('/logout', methods=['POST'])
def logout():
    """Cierra la sesión local y redirige al inicio."""
    session.clear()
    return redirect(url_for('main.index'))


# ─── Rutas de UI ──────────────────────────────────────────────────────────────
@main_bp.route('/')
def index():
    """Renderiza la página principal con todas las tarjetas de funciones."""
    return render_template('index.html', output_file=None)


@main_bp.route('/index')
def index_alt():
    """Redirect /index to / for consistency."""
    return redirect(url_for('main.index'))


@main_bp.route('/reorder_ui')
def reorder_ui():
    """Renderiza la página de ordenar PDF."""
    return render_template('reorder.html')


@main_bp.route('/organize_ui')
def organize_ui():
    """Renderiza la página de organizar PDF."""
    return render_template('organize.html')


@main_bp.route('/unir_ui')
def unir_ui():
    """Renderiza la página de unir PDFs."""
    return render_template('unir.html')


@main_bp.route('/crop_ui')
def crop_ui():
    """Renderiza la página de crop PDF."""
    return render_template('crop.html')


@main_bp.route('/edit_ui')
def edit_ui():
    """Renderiza la página de editar PDF."""
    return render_template('edit.html')


@main_bp.route('/cerrar_sesion', methods=['POST'])
def cerrar_sesion():
    """
    Limpieza manual de archivos activada por el usuario.
    El botón 'Limpiar archivos' del header apunta a esta ruta.
    Elimina todos los archivos en /uploads y /outputs y redirige al inicio.
    """
    limpiar_carpeta(UPLOAD_FOLDER)
    limpiar_carpeta(OUTPUT_FOLDER)
    return render_template('index.html', output_file=None)


@main_bp.route('/download/<path:filename>')
def download_file(filename):
    """
    Sirve un archivo desde la carpeta /outputs para descarga.

    Valida que el nombre no contenga rutas relativas ("..") ni separadores
    de directorio para prevenir path traversal. También elimina el Mark of
    the Web (MOTW) del archivo servido en sistemas Windows.

    Args:
        filename (str): Nombre del archivo a descargar (solo nombre base).

    Returns:
        Response: Archivo como adjunto descargable.

    Raises:
        400: Si el nombre contiene "..", "/" o "\" (intento de traversal).
    """
    # FIX HIGH: validación de path traversal — solo nombre base permitido
    if '..' in filename or '/' in filename or '\\' in filename:
        return 'Nombre de archivo inválido.', 400

    # Confirmar que la ruta resultante está dentro de OUTPUT_FOLDER
    ruta_absoluta = os.path.realpath(os.path.join(OUTPUT_FOLDER, filename))
    if not ruta_absoluta.startswith(os.path.realpath(OUTPUT_FOLDER) + os.sep):
        return 'Nombre de archivo inválido.', 400

    # Eliminar Mark of the Web del archivo (no-op en Linux/Docker)
    eliminar_motw(ruta_absoluta)

    return send_from_directory(OUTPUT_FOLDER, filename)


@main_bp.route('/convert', methods=['POST'])
def convert():
    """
    Convierte un PDF a formato Word (.docx) usando pdf2docx.

    Parámetros del formulario:
        pdf_file (file): Archivo PDF a convertir.

    Returns:
        Response: Template con enlace al archivo Word generado.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    # Sanitizar nombre: reemplazar caracteres especiales por guion bajo
    nombre_base = os.path.splitext(file.filename)[0]
    nombre_limpio = re.sub(r'[^\w\-.]', '_', nombre_base)
    filename = secure_filename(nombre_limpio + '.pdf')

    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    # Validar antes de procesar
    try:
        doc = fitz.open(pdf_path)

        if doc.is_encrypted:
            doc.close()
            return 'El PDF está protegido con contraseña. Desbloquéalo primero.', 400

        total_paginas = doc.page_count
        doc.close()

        if total_paginas > 60:
            return f'El PDF tiene {total_paginas} páginas. El límite es 30 páginas.', 400

    except Exception as e:
        return f'No se pudo leer el PDF: {str(e)}', 400

    # Conservar nombre original limpio en el output
    output_filename = nombre_limpio + '.docx'
    word_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        cv = Converter(pdf_path)
        cv.convert(word_path, start=0, end=None)
        cv.close()
    except Exception as e:
        return f'Error al convertir el archivo: {str(e)}', 500

    output_file_url = f'/download/{output_filename}'
    return render_template('index.html', output_file=output_file_url, convirtiendo=False)


@main_bp.route('/pdf_to_pptx', methods=['POST'])
def pdf_to_pptx():
    """
    Convierte un PDF a presentación PowerPoint (.pptx).

    Cada página del PDF se renderiza como imagen PNG a 200 DPI y se inserta
    como una diapositiva de tamaño carta en el PPTX generado.

    IMPORTANTE: El resultado NO es texto editable. Cada diapositiva es una
    imagen a página completa del PDF original. No se recupera ni texto ni
    elementos vectoriales.

    Args:
        pdf_file (file): Archivo PDF a convertir.

    Returns:
        Response: Template con enlace al archivo PPTX generado.

    Raises:
        400: Si no se selecciona archivo, no es PDF o está encriptado.
        500: Si ocurre un error durante el renderizado o la generación.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    nombre_base = os.path.splitext(file.filename)[0]
    nombre_limpio = re.sub(r'[^\w\-.]', '_', nombre_base)
    pdf_filename = secure_filename(nombre_limpio + '.pdf')
    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
    file.save(pdf_path)

    output_filename = nombre_limpio + '.pptx'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        if doc.is_encrypted:
            doc.close()
            return 'El PDF está protegido con contraseña. Desbloquéalo primero.', 400

        prs = Presentation()
        # Tamaño carta (8.5x11 pulgadas) en formato 16:9 horizontal
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]

        for page in doc:
            # Renderizar la página a PNG a 200 DPI en memoria
            pixmap = page.get_pixmap(dpi=200)
            img_bytes = pixmap.tobytes('png')
            img_io = io.BytesIO(img_bytes)

            slide = prs.slides.add_slide(blank_layout)
            slide.shapes.add_picture(
                img_io,
                left=0,
                top=0,
                width=prs.slide_width,
                height=prs.slide_height
            )

        doc.close()
        prs.save(output_path)

    except Exception as e:
        return f'Error al convertir el archivo: {str(e)}', 500

    # Limpiar Mark of the Web del archivo generado (no-op en Linux/Docker)
    eliminar_motw(output_path)

    return render_template('index.html', output_file=f'/download/{output_filename}')


@main_bp.route('/pptx_to_pdf', methods=['POST'])
def pptx_to_pdf():
    """
    Convierte una presentación PowerPoint (.pptx) a PDF.

    Invoca LibreOffice en modo headless para realizar la conversión,
    preservando el texto y elementos editables como contenido del PDF.

    Args:
        pptx_file (file): Archivo PPTX a convertir.

    Returns:
        Response: Template con enlace al archivo PDF generado.

    Raises:
        400: Si no se selecciona archivo o no es PPTX.
        500: Si LibreOffice falla, se agota el tiempo o no genera el PDF.
    """
    if 'pptx_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pptx_file']

    if file.filename == '' or not file.filename.lower().endswith('.pptx'):
        return 'Por favor, suba un archivo PPTX.', 400

    pptx_filename = secure_filename(file.filename)
    pptx_path = os.path.join(UPLOAD_FOLDER, pptx_filename)
    file.save(pptx_path)

    nombre_base = os.path.splitext(pptx_filename)[0]
    output_filename = nombre_base + '.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    # Ruta del binario de LibreOffice. En Linux (Docker) está en PATH;
    # en Windows se busca en la ubicación típica de instalación.
    libreoffice_bin = 'libreoffice'
    if os.name == 'nt':
        rutas_windows = [
            r'C:\Program Files\LibreOffice\program\soffice.exe',
            r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        ]
        for ruta in rutas_windows:
            if os.path.exists(ruta):
                libreoffice_bin = ruta
                break

    try:
        subprocess.run(
            [
                libreoffice_bin,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', OUTPUT_FOLDER,
                pptx_path
            ],
            check=True,
            timeout=120,
            capture_output=True
        )
    except subprocess.TimeoutExpired:
        return 'La conversión tardó demasiado. Intenta con un archivo más pequeño.', 500
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return f'No se pudo convertir el archivo con LibreOffice: {str(e)}', 500

    if not os.path.exists(output_path):
        return 'LibreOffice no generó el PDF esperado.', 500

    # Limpiar Mark of the Web del archivo generado (no-op en Linux/Docker)
    eliminar_motw(output_path)

    return render_template('index.html', output_file=f'/download/{output_filename}')