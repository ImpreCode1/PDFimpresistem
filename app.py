from flask import Flask, request, render_template, send_from_directory
from pdf2docx import Converter
import fitz
import io
import os
import zipfile
from flask import send_file
from werkzeug.utils import secure_filename  # agregar al import existente
import pikepdf             # PDF a PDF/A
import pdfplumber
from openpyxl import Workbook
import pytesseract         # OCR PDF


app = Flask(__name__)

# Directorio donde se guardarán los archivos cargados y convertidos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER', os.path.join(BASE_DIR, 'outputs'))

# Crear los directorios si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html', output_file=None)

# PDF a JPG
@app.route('/pdf_to_jpg', methods=['POST'])
def pdf_to_jpg():
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
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, page in enumerate(doc):
                pixmap = page.get_pixmap(dpi=dpi)
                formato_pymupdf = 'jpg' if image_format == 'jpg' else 'png'
                extension = 'jpg' if image_format == 'jpg' else 'png'
                img_bytes = pixmap.tobytes(formato_pymupdf)
                nombre_imagen = f"{nombre_base}_pagina_{i + 1}.{extension}"
                zipf.writestr(nombre_imagen, img_bytes)

        doc.close()
        buffer.seek(0)

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{nombre_base}_imagenes_{image_format}.zip'
    )

# Extraer PDF
def parsear_paginas(texto, total_paginas):
    paginas = set()
    partes = texto.split(',')
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if '-' in parte:
            extremos = parte.split('-', 1)
            if len(extremos) != 2 or not extremos[0].strip() or not extremos[1].strip():
                raise ValueError('Formato de rango inválido.')
            inicio = int(extremos[0])
            fin = int(extremos[1])
            if inicio > fin:
                raise ValueError('El rango de páginas debe ir de menor a mayor.')
            for n in range(inicio, fin + 1):
                paginas.add(n - 1)
        else:
            paginas.add(int(parte) - 1)
    return sorted([p for p in paginas if 0 <= p < total_paginas])

@app.route('/extract', methods=['POST'])
def extract_pages():
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

#PDF a Excel
@app.route('/pdf_to_excel', methods=['POST'])
def pdf_to_excel():
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    output_filename = file.filename.rsplit('.', 1)[0] + '.xlsx'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        wb = Workbook()
        wb.remove(wb.active)  # eliminar hoja vacía por defecto
        tablas_encontradas = 0

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tablas = page.extract_tables()

                for tabla_num, tabla in enumerate(tablas):
                    if not tabla:
                        continue

                    tablas_encontradas += 1
                    nombre_hoja = f"Pag{page_num + 1}_Tabla{tabla_num + 1}"
                    ws = wb.create_sheet(title=nombre_hoja)

                    for fila in tabla:
                        fila_limpia = [
                            celda if celda is not None else ''
                            for celda in fila
                        ]
                        ws.append(fila_limpia)

        if tablas_encontradas == 0:
            return 'No se encontraron tablas en el PDF.', 400

        wb.save(output_path)

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

# HTML a PDF
@app.route('/html_to_pdf', methods=['POST'])
def html_to_pdf():
    html_file = request.files.get('html_file')
    html_string = request.form.get('html_string', '').strip()

    # Import diferido para no romper el arranque de Flask si faltan dependencias nativas.
    try:
        from weasyprint import HTML as WeasyprintHTML
    except Exception:
        return 'No se pudo inicializar HTML a PDF. Instala las dependencias de WeasyPrint en el sistema.', 500

    # Verificar que venga al menos una fuente
    tiene_archivo = html_file and html_file.filename != ''
    tiene_string = bool(html_string)

    if not tiene_archivo and not tiene_string:
        return 'Por favor, sube un archivo HTML o pega el código HTML.', 400

    if tiene_archivo and not html_file.filename.endswith('.html'):
        return 'Por favor, sube un archivo con extensión .html', 400

    output_filename = 'documento_convertido.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        if tiene_archivo:
            html_filename = secure_filename(html_file.filename)
            html_path = os.path.join(UPLOAD_FOLDER, html_filename)
            html_file.save(html_path)
            WeasyprintHTML(filename=html_path).write_pdf(output_path)
        else:
            WeasyprintHTML(string=html_string).write_pdf(output_path)

    except Exception as e:
        return f'Error al convertir el HTML: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

#Reparar PDF
@app.route('/repair', methods=['POST'])
def repair_pdf():
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    output_filename = file.filename.rsplit('.', 1)[0] + '_reparado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        # Forzar lectura completa del documento
        for page in doc:
            _ = page.get_text()

        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True,
            linear=True
        )
        doc.close()

    except Exception as e:
        return f'No se pudo reparar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

#PDF a PDF/A
@app.route('/pdf_to_pdfa', methods=['POST'])
def pdf_to_pdfa():
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    output_filename = file.filename.rsplit('.', 1)[0] + '_pdfa.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        with pikepdf.open(pdf_path) as pdf:
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

#Rellenar Formulario PDF
@app.route('/form_filler', methods=['POST'])
def form_filler():
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    try:
        doc = fitz.open(pdf_path)
        campos = []

        for page_num, page in enumerate(doc):
            for field in page.widgets():
                if field.field_type in [
                    fitz.PDF_WIDGET_TYPE_TEXT,
                    fitz.PDF_WIDGET_TYPE_CHECKBOX,
                    fitz.PDF_WIDGET_TYPE_LISTBOX
                ]:
                    campos.append({
                        'nombre': field.field_name,
                        'tipo': field.field_type,
                        'valor_actual': field.field_value or '',
                        'pagina': page_num
                    })

        doc.close()

        if not campos:
            return 'Este PDF no contiene campos de formulario.', 400

    except Exception as e:
        return f'Error al leer el formulario: {str(e)}', 500

    return render_template(
        'form_filler.html',
        campos=campos,
        pdf_nombre=file.filename
    )
@app.route('/form_filler/guardar', methods=['POST'])
def form_filler_guardar():
    pdf_nombre = request.form.get('pdf_nombre', '')

    if not pdf_nombre:
        return 'Nombre de archivo no encontrado.', 400

    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_nombre)

    if not os.path.exists(pdf_path):
        return 'El archivo original ya no está disponible. Sube el PDF nuevamente.', 400

    output_filename = pdf_nombre.rsplit('.', 1)[0] + '_rellenado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        for page in doc:
            for field in page.widgets():
                nombre = field.field_name
                valor = request.form.get(nombre, '')

                if field.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    field.field_value = valor == 'on'
                else:
                    field.field_value = valor

                field.update()

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al guardar el formulario: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

#

#Firmar PDF
@app.route('/sign', methods=['POST'])
def sign_pdf():
    if 'pdf_file' not in request.files or 'firma_file' not in request.files:
        return 'Por favor, sube el PDF y la imagen de tu firma.', 400

    file = request.files['pdf_file']
    firma = request.files['firma_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF válido.', 400

    extensiones_firma = {'.jpg', '.jpeg', '.png'}
    ext_firma = os.path.splitext(firma.filename)[1].lower()
    if ext_firma not in extensiones_firma:
        return 'La firma debe ser una imagen JPG o PNG.', 400

    try:
        pagina_num = max(1, int(request.form.get('pagina', 1)))
        pos_x = max(0, min(90, int(request.form.get('pos_x', 60))))
        pos_y = max(0, min(90, int(request.form.get('pos_y', 80))))
        firma_ancho = max(5, min(50, int(request.form.get('firma_ancho', 30))))
        firma_alto = max(5, min(30, int(request.form.get('firma_alto', 10))))
    except ValueError:
        return 'Los valores de posición deben ser números enteros.', 400

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    output_filename = file.filename.rsplit('.', 1)[0] + '_firmado.pdf'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        doc = fitz.open(pdf_path)

        if pagina_num > doc.page_count:
            doc.close()
            return f'El PDF solo tiene {doc.page_count} páginas.', 400

        page = doc[pagina_num - 1]
        ancho = page.rect.width
        alto = page.rect.height

        x0 = ancho * (pos_x / 100)
        y0 = alto * (pos_y / 100)
        x1 = x0 + ancho * (firma_ancho / 100)
        y1 = y0 + alto * (firma_alto / 100)

        firma_bytes = firma.read()
        page.insert_image(fitz.Rect(x0, y0, x1, y1), stream=firma_bytes)

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al firmar el documento: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')



# Recortar PDF
@app.route('/crop', methods=['POST'])
def crop_pdf():
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']

    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    try:
        margen_izq = max(0, min(40, int(request.form.get('margen_izq', 0))))
        margen_der = max(0, min(40, int(request.form.get('margen_der', 0))))
        margen_sup = max(0, min(40, int(request.form.get('margen_sup', 0))))
        margen_inf = max(0, min(40, int(request.form.get('margen_inf', 0))))
    except ValueError:
        return 'Los márgenes deben ser números enteros.', 400

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

# Marca de agua PDF
@app.route('/watermark', methods=['POST'])
def watermark_pdf():
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

            # Punto central de la página
            centro_x = ancho / 2
            centro_y = alto / 2

            # Insertar texto rotado 45 grados en el centro
            page.insert_text(
                fitz.Point(centro_x - 150, centro_y),
                texto,
                fontsize=60,
                color=(0.6, 0.6, 0.6),
                rotate=45,
                fill_opacity=0.3
            )

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

# Aplanar PDF
@app.route('/flatten', methods=['POST'])
def flatten_pdf():
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
            # Aplanar anotaciones
            annots = page.annots()
            if annots:
                for annot in annots:
                    annot.update()

            # Eliminar campos de formulario
            widgets = page.widgets()
            if widgets:
                for field in widgets:
                    page.delete_widget(field)

            # Fusionar capas
            page.clean_contents()

        doc.save(output_path, deflate=True)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')



# Ordenar PDF
@app.route('/reorder', methods=['POST'])
def reorder_pdf():
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

        # Validar que estén todas las páginas exactamente una vez
        if len(indices) != total or sorted(indices) != list(range(total)):
            doc.close()
            return f'Debes incluir todas las {total} páginas exactamente una vez.', 400

        doc.select(indices)
        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

# Organizar PDF
@app.route('/organize', methods=['POST'])
def organize_pdf():
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

        if len(indices_eliminar) >= total:
            doc.close()
            return 'No puedes eliminar todas las páginas del documento.', 400

        indices_conservar = [i for i in range(total) if i not in indices_eliminar]

        doc.select(indices_conservar)
        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

# Número de páginas PDF
@app.route('/page_numbers', methods=['POST'])
def page_numbers_pdf():
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
            numero = i + 1
            ancho = page.rect.width
            alto = page.rect.height
            texto = f"Página {numero} de {total}"

            if posicion == 'centro':
                x = ancho / 2 - 30
                y = alto - 20
            elif posicion == 'derecha':
                x = ancho - 80
                y = alto - 20
            elif posicion == 'izquierda':
                x = 20
                y = alto - 20
            else:
                x = ancho / 2 - 30
                y = alto - 20

            page.insert_text(
                fitz.Point(x, y),
                texto,
                fontsize=10,
                color=(0, 0, 0)
            )

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

# Comprimir PDF
@app.route('/compress', methods=['POST'])
def compress_pdf():
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
        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True
        )
        doc.close()

        tamaño_original = os.path.getsize(pdf_path)
        tamaño_comprimido = os.path.getsize(output_path)
        ahorro = round((1 - tamaño_comprimido / tamaño_original) * 100, 1)

        if ahorro < 0:
            ahorro = 0

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template(
        'index.html',
        output_file=f'/download/{output_filename}',
        ahorro=ahorro
    )

# JPG a PDF
@app.route('/jpg_to_pdf', methods=['POST'])
def jpg_to_pdf():
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
            img_temp = fitz.open(stream=imagen_bytes, filetype=filetype)
            rect = img_temp[0].rect
            img_temp.close()

            page = doc.new_page(width=rect.width, height=rect.height)
            page.insert_image(rect, stream=imagen_bytes)

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar las imágenes: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')



# Desencriptar/Descifrar PDF
@app.route('/unlock', methods=['POST'])
def unlock_pdf():
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

        if not doc.is_encrypted:
            doc.close()
            return 'Este PDF no está protegido con contraseña.', 400

        resultado = doc.authenticate(password)
        if resultado == 0:
            doc.close()
            return 'Contraseña incorrecta.', 400

        doc.save(output_path)
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

# Encriptar/Cifrar PDF
@app.route('/protect', methods=['POST'])
def protect_pdf():
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
            user_pwd=password,
            owner_pwd=password + "_owner",
            encryption=fitz.PDF_ENCRYPT_AES_256
        )
        doc.close()

    except Exception as e:
        return f'Error al procesar el archivo: {str(e)}', 500

    return render_template('index.html', output_file=f'/download/{output_filename}')

# Rotar PDF
@app.route('/rotate', methods=['POST'])
def rotate_pdf():
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

    doc = fitz.open(pdf_path)
    for page in doc:
        page.set_rotation(angulo)
    doc.save(output_path)
    doc.close()

    return render_template('index.html', output_file=f'/download/{output_filename}')

@app.route('/convert', methods=['POST'])
def convert():
    # Verificar si el archivo fue cargado
    if 'pdf_file' not in request.files:
        return 'No se ha seleccionado un archivo.', 400

    file = request.files['pdf_file']
    
    # Verificar que el archivo sea un PDF
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return 'Por favor, suba un archivo PDF.', 400

    # Guardar el archivo PDF cargado
    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    # Crear el nombre del archivo de salida
    output_filename = filename.rsplit('.', 1)[0] + '.docx'
    word_path = os.path.join(OUTPUT_FOLDER, output_filename)

    # Realizar la conversión de PDF a Word
    cv = Converter(pdf_path)
    cv.convert(word_path, start=0, end=None)
    cv.close()

    # Proveer el enlace para descargar el archivo Word convertido
    output_file_url = f'/download/{output_filename}'
    return render_template('index.html', output_file=output_file_url)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)
# Aquí es donde asignas la variable `application` para que mod_wsgi la encuentre
application = app  # Asigna 'app' a 'application'

# Si estás ejecutando localmente, puedes usar esto para pruebas en desarrollo:
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080, debug=True)
