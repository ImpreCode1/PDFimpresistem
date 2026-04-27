# routes/main.py — Blueprint: main

from flask import Blueprint, request, render_template, send_from_directory
from utils import limpiar_carpeta
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from werkzeug.utils import secure_filename
from pdf2docx import Converter
import os

main_bp = Blueprint('main', __name__)


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


@main_bp.route('/')

def index():
    """Renderiza la página principal con todas las tarjetas de funciones."""
    return render_template('index.html', output_file=None)


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

    Args:
        filename (str): Nombre del archivo a descargar.

    Returns:
        Response: Archivo como adjunto descargable.
    """
    return send_from_directory(OUTPUT_FOLDER, filename)


@main_bp.route('/convert', methods=['POST'])
def convert():
    """
    Convierte un PDF a formato Word (.docx) usando pdf2docx.

    Esta ruta existía antes del desarrollo del proyecto actual y se mantiene
    por compatibilidad. Usa la librería pdf2docx que intenta preservar
    el formato del documento original.

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

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '.docx'
    word_path = os.path.join(OUTPUT_FOLDER, output_filename)

    cv = Converter(pdf_path)
    cv.convert(word_path, start=0, end=None)
    cv.close()

    output_file_url = f'/download/{output_filename}'
    return render_template('index.html', output_file=output_file_url)