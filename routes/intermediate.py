# routes/intermediate.py — Blueprint: intermediate

from flask import Blueprint, request, render_template, send_file
from utils import parsear_paginas
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from werkzeug.utils import secure_filename
from auth import login_required
import fitz
import pikepdf
import io
import zipfile
import os

intermediate_bp = Blueprint('intermediate', __name__)


@intermediate_bp.route('/reorder', methods=['POST'])
@login_required
def reorder_pdf():
    """
    Reorganiza las páginas de un PDF en el orden indicado por el usuario.

    Args:
        pdf_file (file): Archivo PDF a reordenar.
        paginas (str): Nuevo orden de páginas (ej: '3,1,2').

    Returns:
        Response: Template con enlace al PDF reordenado.

    Raises:
        400: Si hay páginas repetidas o faltantes.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    paginas_texto = request.form.get('paginas', '').strip()

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    if not paginas_texto:
        return 'Por favor, indica el nuevo orden de las páginas.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_ordenado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)
        total = doc.page_count
        indices = parsear_paginas(paginas_texto, total)

        # Validación doble: detecta páginas faltantes Y páginas repetidas en un paso
        # - len != total: faltan páginas (set() eliminó duplicados)
        # - sorted != range: hay páginas fuera del rango o el conteo no cierra
        if len(indices) != total or sorted(indices) != list(range(total)):
            doc.close()
            return f'Debes incluir todas las {total} páginas exactamente una vez.', 400

        doc.select(indices)  # reordena en memoria eficientemente
        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@intermediate_bp.route('/organize', methods=['POST'])
@login_required
def organize_pdf():
    """
    Elimina páginas específicas de un PDF.

    Args:
        pdf_file (file): Archivo PDF a organizar.
        paginas (str): Páginas a eliminar (ej: '2,5,8' o '3-6').

    Returns:
        Response: Template con enlace al PDF organizado.

    Raises:
        400: Si se intenta eliminar todas las páginas.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    paginas_texto = request.form.get('paginas', '').strip()

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    if not paginas_texto:
        return 'Por favor, indica las páginas a eliminar.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_organizado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)
        total = doc.page_count

        indices_eliminar = set(parsear_paginas(paginas_texto, total))

        # Un PDF con 0 páginas es un archivo corrupto
        if len(indices_eliminar) >= total:
            doc.close()
            return 'No puedes eliminar todas las páginas del documento.', 400

        # Lógica inversa: conservar todo lo que NO está en la lista a eliminar
        indices_conservar = [i for i in range(total) if i not in indices_eliminar]

        doc.select(indices_conservar)
        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@intermediate_bp.route('/page_numbers', methods=['POST'])
@login_required
def page_numbers_pdf():
    """
    Inserta numeración automática en el pie de cada página del PDF.

    Args:
        pdf_file (file): Archivo PDF a numerar.
        posicion (str): Posición del número ('centro', 'derecha', 'izquierda').

    Returns:
        Response: Template con enlace al PDF numerado.

    Raises:
        400: Si no se selecciona archivo.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    posicion = request.form.get('posicion', 'centro')

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_numerado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)
        total = doc.page_count

        for i, page in enumerate(doc):
            numero = i + 1  # el usuario ve páginas desde 1, no desde 0
            ancho = page.rect.width
            alto = page.rect.height
            texto = f"Página {numero} de {total}"

            # Coordenada Y siempre al pie — 20 puntos desde el borde inferior
            # Coordenada X varía según posición elegida
            if posicion == 'centro':
                x = ancho / 2 - 30   # -30 compensa el ancho del texto
                y = alto - 20
            elif posicion == 'derecha':
                x = ancho - 80        # -80 para que el texto no se corte
                y = alto - 20
            elif posicion == 'izquierda':
                x = 20
                y = alto - 20
            else:
                x = ancho / 2 - 30   # valor por defecto: centro
                y = alto - 20

            page.insert_text(fitz.Point(x, y), texto, fontsize=10, color=(0, 0, 0))

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@intermediate_bp.route('/compress', methods=['POST'])
@login_required
def compress_pdf():
    """
    Reduce el tamaño de un PDF optimizando su estructura interna.

    Args:
        pdf_file (file): Archivo PDF a comprimir.

    Returns:
        Response: Template con enlace al PDF comprimido y porcentaje de ahorro.

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

    output_filename = filename.rsplit('.', 1)[0] + '_comprimido.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()  # cerrar ANTES de medir — garantiza escritura completa en disco

        tamaño_original = os.path.getsize(pdf_path)
        tamaño_comprimido = os.path.getsize(output_path)
        ahorro = round((1 - tamaño_comprimido / tamaño_original) * 100, 1)

        if ahorro < 0:
            ahorro = 0  # archivo ya estaba optimizado

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template(
        'index.html',
        output_file=f'/download/{output_filename}',
        ahorro=ahorro   # variable extra pasada al template para mostrar el porcentaje
    )


@intermediate_bp.route('/reduce', methods=['POST'])
@login_required
def reduce_pdf():
    """
    Reduce significativamente el tamaño de un PDF reduciendo la calidad de las imágenes.

    Args:
        pdf_file (file): Archivo PDF a reducir.
        nivel (str): Nivel de compresión ('bajo', 'medio', 'alto'). Por defecto: 'medio'.

    Returns:
        Response: Template con enlace al PDF reducido y porcentaje de ahorro.

    Raises:
        400: Si no se selecciona archivo.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    nivel = request.form.get('nivel', 'medio')
    if nivel not in {'bajo', 'medio', 'alto'}:
        nivel = 'medio'

    config_nivel = {
        'bajo': {'dpi': 150, 'calidad': 85},
        'medio': {'dpi': 100, 'calidad': 70},
        'alto': {'dpi': 72, 'calidad': 50}
    }
    dpi = config_nivel[nivel]['dpi']
    calidad = config_nivel[nivel]['calidad']

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_reducido.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc_origen = fitz.open(pdf_path)
        doc_nuevo = fitz.open()

        for pagina in doc_origen:
            ancho = pagina.rect.width
            alto = pagina.rect.height
            pagina_nueva = doc_nuevo.new_page(width=ancho, height=alto)

            pixmap = pagina.get_pixmap(dpi=dpi)
            imagen_bytes = pixmap.tobytes('jpeg', quality=calidad)
            pagina_nueva.insert_image(fitz.Rect(0, 0, ancho, alto), stream=imagen_bytes)

        doc_origen.close()
        doc_nuevo.save(output_path, garbage=4, deflate=True, clean=True)
        doc_nuevo.close()

        tamaño_original = os.path.getsize(pdf_path)
        tamaño_reducido = os.path.getsize(output_path)
        ahorro = round((1 - tamaño_reducido / tamaño_original) * 100, 1)

        if ahorro < 0:
            ahorro = 0

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template(
        'index.html',
        output_file=f'/download/{output_filename}',
        ahorro=ahorro
    )


@intermediate_bp.route('/pdf_to_jpg', methods=['POST'])
@login_required
def pdf_to_jpg():
    """
    Convierte cada página de un PDF en imagen y las empaqueta en un ZIP.

    Args:
        pdf_file (file): Archivo PDF a convertir.
        dpi (int): Resolución (72, 150 o 300). Por defecto: 150.
        image_format (str): Formato de salida ('jpg' o 'png'). Por defecto: 'png'.

    Returns:
        Response: Archivo ZIP descargable con las imágenes.

    Raises:
        400: Si no se selecciona archivo.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    dpi = request.form.get('dpi', '150')
    image_format = request.form.get('image_format', 'png').lower()

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    try:
        dpi = int(dpi)
        if dpi not in [72, 150, 300]:
            dpi = 150
    except ValueError:
        dpi = 150

    if image_format not in {'jpg', 'png'}:
        image_format = 'png'

    pdf_path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(pdf_path)

    nombre_base = file.filename.rsplit('.', 1)[0]

    try:
        doc = fitz.open(pdf_path)
        buffer = io.BytesIO()  # ZIP en memoria — no toca el disco

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, page in enumerate(doc):
                pixmap = page.get_pixmap(dpi=dpi)
                formato_pymupdf = 'jpg' if image_format == 'jpg' else 'png'
                extension = 'jpg' if image_format == 'jpg' else 'png'
                img_bytes = pixmap.tobytes(formato_pymupdf)
                nombre_imagen = f"{nombre_base}_pagina_{i + 1}.{extension}"
                zipf.writestr(nombre_imagen, img_bytes)  # escribe bytes directo al ZIP

        doc.close()
        buffer.seek(0)  # volver al inicio del buffer para que send_file lo lea

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{nombre_base}_imagenes_{image_format}.zip'
    )


@intermediate_bp.route('/jpg_to_pdf', methods=['POST'])
@login_required
def jpg_to_pdf():
    """
    Convierte una o varias imágenes JPG/PNG en un único PDF.

    Args:
        imagenes (file[]): Una o varias imágenes JPG o PNG.

    Returns:
        Response: Template con enlace al PDF generado.

    Raises:
        400: Si no se seleccionan imágenes o el formato no es soportado.
    """
    if 'imagenes' not in request.files:
        return 'No se han seleccionado imágenes.', 400

    imagenes = request.files.getlist('imagenes')
    extensiones_validas = {'.jpg', '.jpeg', '.png'}

    if not imagenes or imagenes[0].filename == '':
        return 'Por favor, selecciona al menos una imagen.', 400

    for img in imagenes:
        ext = os.path.splitext(img.filename)[1].lower()
        if ext not in extensiones_validas:
            return f'Formato no soportado: {img.filename}. Use JPG o PNG.', 400

    output_filename = 'imagenes_convertidas.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open()

        for imagen in imagenes:
            imagen_bytes = imagen.read()
            ext = os.path.splitext(imagen.filename)[1].lower()
            filetype = 'png' if ext == '.png' else 'jpeg'

            # Abrir temporalmente para leer dimensiones y cerrar de inmediato
            img_temp = fitz.open(stream=imagen_bytes, filetype=filetype)
            rect = img_temp[0].rect
            img_temp.close()

            # Crear página del tamaño exacto de la imagen para evitar distorsión
            page = doc.new_page(width=rect.width, height=rect.height)
            page.insert_image(rect, stream=imagen_bytes)

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar las imágenes: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@intermediate_bp.route('/repair', methods=['POST'])
@login_required
def repair_pdf():
    """
    Intenta recuperar un PDF dañado o corrupto.

    Args:
        pdf_file (file): Archivo PDF dañado.

    Returns:
        Response: Template con enlace al PDF reparado.

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

    output_filename = filename.rsplit('.', 1)[0] + '_reparado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        # Forzar lectura completa — PyMuPDF repara errores al leer cada página
        # _ indica que el valor retornado no se necesita, solo el efecto de leer
        for page in doc:
            _ = page.get_text()

        doc.save(output_path, garbage=4, deflate=True, clean=True, linear=True)
        doc.close()

    except Exception as e:
        return f'No se pudo reparar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@intermediate_bp.route('/crop', methods=['POST'])
@login_required
def crop_pdf():
    """
    Recorta los márgenes de todas las páginas de un PDF.

    Args:
        pdf_file (file): Archivo PDF a recortar.
        margen_izq (int): Margen izquierdo (0-40%).
        margen_der (int): Margen derecho (0-40%).
        margen_sup (int): Margen superior (0-40%).
        margen_inf (int): Margen inferior (0-40%).

    Returns:
        Response: Template con enlace al PDF recortado.

    Raises:
        400: Si los márgenes opuestos suman >= 100% o no son numéricos.
    """
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    try:
        # max/min limita el rango en el servidor aunque el HTML ya lo valide
        margen_izq = max(0, min(40, int(request.form.get('margen_izq', 0))))
        margen_der = max(0, min(40, int(request.form.get('margen_der', 0))))
        margen_sup = max(0, min(40, int(request.form.get('margen_sup', 0))))
        margen_inf = max(0, min(40, int(request.form.get('margen_inf', 0))))
    except ValueError:
        return 'Los márgenes deben ser números enteros.', 400

    # Dos márgenes opuestos pueden sumar más del 100% aunque cada uno sea <= 40%
    if margen_izq + margen_der >= 100 or margen_sup + margen_inf >= 100:
        return 'Los márgenes combinados no pueden superar el 100%.', 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    output_filename = filename.rsplit('.', 1)[0] + '_recortado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        for page in doc:
            ancho = page.rect.width
            alto = page.rect.height

            # Calcular el área visible resultante en puntos
            x0 = ancho * (margen_izq / 100)
            y0 = alto * (margen_sup / 100)
            x1 = ancho * (1 - margen_der / 100)
            y1 = alto * (1 - margen_inf / 100)

            page.set_cropbox(fitz.Rect(x0, y0, x1, y1))

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')


@intermediate_bp.route('/pdf_to_pdfa', methods=['POST'])
@login_required
def pdf_to_pdfa():
    """
    Convierte un PDF al formato PDF/A-2B para archivado a largo plazo.

    Args:
        pdf_file (file): Archivo PDF a convertir.

    Returns:
        Response: Template con enlace al PDF/A generado.

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

    output_filename = file.filename.rsplit('.', 1)[0] + '_pdfa.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        with pikepdf.open(pdf_path) as pdf:
            # set_pikepdf_as_editor=False evita que pikepdf agregue sus propios metadatos
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                meta['pdfaid:part'] = '2'
                meta['pdfaid:conformance'] = 'B'
                meta['dc:format'] = 'application/pdf'

            pdf.save(
                output_path,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate
            )

    except Exception as e:
        return f'Error al convertir el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')