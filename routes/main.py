# routes/main.py — Blueprint: main

from flask import Blueprint, request, render_template, send_from_directory, redirect, url_for, session
from utils import limpiar_carpeta
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from werkzeug.utils import secure_filename
from auth import login_required
import fitz
from pdf2docx import Converter
import os
import re

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
@login_required
def index():
    """Renderiza la página principal con todas las tarjetas de funciones."""
    return render_template('index.html', output_file=None)


@main_bp.route('/index')
def index_alt():
    """Redirect /index to / for consistency."""
    return redirect(url_for('main.index'))


@main_bp.route('/reorder_ui')
@login_required
def reorder_ui():
    """Renderiza la página de ordenar PDF."""
    return render_template('reorder.html')


@main_bp.route('/organize_ui')
@login_required
def organize_ui():
    """Renderiza la página de organizar PDF."""
    return render_template('organize.html')


@main_bp.route('/unir_ui')
@login_required
def unir_ui():
    """Renderiza la página de unir PDFs."""
    return render_template('unir.html')


@main_bp.route('/crop_ui')
@login_required
def crop_ui():
    """Renderiza la página de crop PDF."""
    return render_template('crop.html')


@main_bp.route('/edit_ui')
@login_required
def edit_ui():
    """Renderiza la página de editar PDF."""
    return render_template('edit.html')


@main_bp.route('/cerrar_sesion', methods=['POST'])
@login_required
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
@login_required
def download_file(filename):
    """
    Sirve un archivo desde la carpeta /outputs para descarga.

    Args:
        filename (str): Nombre del archivo a descargar.

    Returns:
        Response: Archivo como adjunto descargable.
    """
    return send_from_directory(OUTPUT_FOLDER, filename)


@main_bp.route('/convert', methods=['POST'])
@login_required
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