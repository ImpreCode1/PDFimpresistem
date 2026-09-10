# routes/main.py — Blueprint: main

from flask import Blueprint, request, render_template, send_from_directory, redirect, url_for, session
from auth import validar_token, login_required
import jwt
from utils import limpiar_carpeta, eliminar_motw
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from werkzeug.utils import secure_filename
import fitz
from pdf2docx import Converter
from pptx import Presentation
from pptx.util import Inches
import os
import re
import io

main_bp = Blueprint('main', __name__)


# ─── Ruta para servir el logo ─────────────────────────────────────────────
@main_bp.route('/logos/<path:filename>')
def serve_logo(filename):
    """Sirve imágenes de la raíz del proyecto."""
    from config import BASE_DIR
    return send_from_directory(BASE_DIR, filename)


# ─── Cierre de sesión ─────────────────────────────────────────────────────
@main_bp.route('/logout')
def logout():
    """
    Cierra la sesión Flask y redirige al login de Hydra Hub.

    Returns:
        Response: Redirect al login central de Impresistem.
    """
    session.clear()
    return redirect("https://central.impresistem.com/login")


# ─── Autenticación SSO Hydra ─────────────────────────────────────────────
@main_bp.route('/auth')
def auth():
    """
    Recibe el JWT de Hydra Hub como parámetro de URL, lo valida,
    crea la sesión Flask con los datos del payload y redirige
    limpiando la URL.

    Args (query params):
        token (str): JWT firmado HS256 proporcionado por Hydra Hub.

    Returns:
        Response: Redirect a la página principal tras crear la sesión.

    Raises:
        400: Si el parámetro token falta o el JWT es inválido/expirado.
    """
    token = request.args.get("token")
    if not token:
        return "Falta el parámetro token.", 400
    try:
        payload = validar_token(token)
    except jwt.ExpiredSignatureError:
        return "El token ha expirado. Solicita uno nuevo.", 401
    except jwt.InvalidTokenError as e:
        return f"Token inválido: {str(e)}", 401

    session.permanent = True
    session["user"] = {
        "sub": payload["sub"],
        "email": payload["email"],
        "name": payload["name"],
        "roles": payload.get("roles", []),
        "positionId": payload.get("positionId"),
        "platform": payload.get("platform"),
    }
    return redirect(url_for("main.index"))


@main_bp.route('/login')
def login_alias():
    """
    Alias de /auth para compatibilidad con el launcher del
    Sistema de Gestión de Accesos.

    Returns:
        Response: Redirect a /auth con los mismos query params.
    """
    return redirect(url_for("main.auth", **request.args))


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


# NOTA: No existe ruta /pptx_to_pdf (conversión PPTX -> PDF) a propósito.
# La conversión a PDF de presentaciones se cubre de forma nativa con
# PowerPoint de escritorio ("Guardar como > PDF"), y así se evita la
# dependencia de LibreOffice (--headless --convert-to pdf), que no está
# instalado ni en plattstest ni en producción.