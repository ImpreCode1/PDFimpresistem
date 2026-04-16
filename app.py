from flask import Flask, request, render_template, send_from_directory
from pdf2docx import Converter
import fitz
import os

app = Flask(__name__)

# Directorio donde se guardarán los archivos cargados y convertidos
UPLOAD_FOLDER = '/var/www/html/PDFimpresistem/uploads'
OUTPUT_FOLDER = '/var/www/html/PDFimpresistem/outputs'

# Crear los directorios si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html', output_file=None)

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

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    output_filename = file.filename.rsplit('.', 1)[0] + '_rotado.docx'
    output_filename = file.filename.rsplit('.', 1)[0] + '_rotado.pdf'
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
    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    # Crear el nombre del archivo de salida
    output_filename = file.filename.rsplit('.', 1)[0] + '.docx'
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
