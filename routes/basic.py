# routes/basic.py — Blueprint: basic

from flask import Blueprint, request, render_template
from utils import parsear_paginas
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from werkzeug.utils import secure_filename
from auth import login_required
import fitz
import os

basic_bp = Blueprint('basic', __name__)


@basic_bp.route('/rotate', methods=['POST'])
@login_required
def rotate_pdf():
    """
    Rota todas las páginas de un PDF en el ángulo indicado (90°, 180° o 270°).

    Args:
        pdf_file (file): Archivo PDF a rotar.
        angulo (str): Ángulo de rotación (90, 180 o 270).

    Returns:
        Response: Template con enlace al PDF rotado.

    Raises:
        400: Si el archivo no es PDF, ángulo inválido o no es numérico.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    angulo = request.form.get('angulo', '90')

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    try:
        angulo = int(angulo)
        if angulo not in [90, 180, 270]:
            return 'Ángulo inválido. Use 90, 180 o 270.', 400
    except ValueError:
        return 'El ángulo debe ser un número.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_rotado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    # set_rotation() aplica la rotación a cada página individualmente
    doc = fitz.open(pdf_path)
    for page in doc:
        page.set_rotation(angulo)
    doc.save(output_path)
    doc.close()

    return render_template('index.html', output_file=f'/download/{output_filename}')


@basic_bp.route('/extract', methods=['POST'])
@login_required
def extract_pages():
    """
    Extrae páginas específicas de un PDF y las guarda en un nuevo documento.

    Args:
        pdf_file (file): Archivo PDF fuente.
        paginas (str): Páginas a extraer (ej: '1,3-5,8').

    Returns:
        Response: Template con enlace al PDF extraído.

    Raises:
        400: Si no se selecciona archivo, campo vacío o sin páginas válidas.
        ValueError: Si el formato de páginas es inválido.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    paginas_texto = request.form.get('paginas', '').strip()

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    if not paginas_texto:
        return 'Por favor, indica las páginas a extraer.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_extraido.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc_original = fitz.open(pdf_path)
        total = doc_original.page_count
        indices = parsear_paginas(paginas_texto, total)

        if not indices:
            return 'No se encontraron páginas válidas en el rango indicado.', 400

        # Crear documento nuevo e insertar solo las páginas seleccionadas
        doc_nuevo = fitz.open()
        for i in indices:
            doc_nuevo.insert_pdf(doc_original, from_page=i, to_page=i)

        doc_nuevo.save(output_path)
        doc_nuevo.close()
        doc_original.close()

    except ValueError as e:
        return f'Formato de páginas inválido: {str(e)}', 400
    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@basic_bp.route('/watermark', methods=['POST'])
@login_required
def watermark_pdf():
    """
    Inserta texto semitransparente en diagonal sobre todas las páginas del PDF.

    Args:
        pdf_file (file): Archivo PDF a marcar.
        texto (str): Texto de marca de agua. Por defecto: 'CONFIDENCIAL'.

    Returns:
        Response: Template con enlace al PDF con marca de agua.

    Raises:
        400: Si no se selecciona archivo o texto vacío.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    texto = request.form.get('texto', 'CONFIDENCIAL').strip()

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    if not texto:
        return 'Por favor, escribe el texto de la marca de agua.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_marcado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        for page in doc:
            ancho = page.rect.width
            alto = page.rect.height

            # El centro se calcula por página porque pueden tener distintos tamaños
            centro_x = ancho / 2
            centro_y = alto / 2

            page.insert_text(
                fitz.Point(centro_x - 150, centro_y),
                texto,
                fontsize=60,
                color=(0.6, 0.6, 0.6),   # gris en formato RGB normalizado
                rotate=45,                 # diagonal
                fill_opacity=0.3           # 30% de opacidad — semitransparente
            )

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@basic_bp.route('/protect', methods=['POST'])
@login_required
def protect_pdf():
    """
    Encripta un PDF con contraseña usando AES-256.

    Args:
        pdf_file (file): Archivo PDF a proteger.
        password (str): Contraseña para abrir el documento.
        confirm_password (str): Confirmación de la contraseña.

    Returns:
        Response: Template con enlace al PDF protegido.

    Raises:
        400: Si la contraseña está vacía, no coincide o tiene menos de 4 caracteres.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    if not password:
        return 'Por favor, ingresa una contraseña.', 400

    if password != confirm_password:
        return 'Las contraseñas no coinciden.', 400

    if len(password) < 4:
        return 'La contraseña debe tener al menos 4 caracteres.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_protegido.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)
        doc.save(
            output_path,
            user_pwd=password,                    # contraseña para abrir
            owner_pwd=password + "_owner",         # contraseña de permisos (oculta al usuario)
            encryption=fitz.PDF_ENCRYPT_AES_256   # estándar de encriptación actual
        )
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@basic_bp.route('/unlock', methods=['POST'])
@login_required
def unlock_pdf():
    """
    Elimina la protección por contraseña de un PDF encriptado.

    Args:
        pdf_file (file): Archivo PDF protegido.
        password (str): Contraseña del documento.

    Returns:
        Response: Template con enlace al PDF desbloqueado.

    Raises:
        400: Si el PDF no está encriptado o la contraseña es incorrecta.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    password = request.form.get('password', '').strip()

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    if not password:
        return 'Por favor, ingresa la contraseña del documento.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_desbloqueado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        # Verificar antes de intentar autenticar — evita comportamiento inesperado
        if not doc.is_encrypted:
            doc.close()
            return 'Este PDF no está protegido con contraseña.', 400

        # authenticate() retorna 0 si la contraseña es incorrecta
        resultado = doc.authenticate(password)
        if resultado == 0:
            doc.close()
            return 'Contraseña incorrecta.', 400

        # Guardar sin user_pwd ni owner_pwd elimina la protección
        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@basic_bp.route('/flatten', methods=['POST'])
@login_required
def flatten_pdf():
    """
    Aplana un PDF convirtiendo anotaciones y campos de formulario en contenido estático.

    Args:
        pdf_file (file): Archivo PDF con formularios o anotaciones.

    Returns:
        Response: Template con enlace al PDF aplanado.

    Raises:
        400: Si no se selecciona archivo.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_aplanado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        for page in doc:
            # Paso 1: aplicar visualmente las anotaciones al contenido base
            annots = page.annots()
            if annots:
                for annot in annots:
                    annot.update()

            # Paso 2: eliminar los campos de formulario interactivos
            widgets = page.widgets()
            if widgets:
                for field in widgets:
                    page.delete_widget(field)

            # Paso 3: fusionar y limpiar las capas de la página
            page.clean_contents()

        # deflate=True compensa el posible aumento de tamaño al fusionar capas
        doc.save(output_path, deflate=True)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')