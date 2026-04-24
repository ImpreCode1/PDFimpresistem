# routes/api.py — Blueprint: api

from flask import Blueprint, request, jsonify, Response, stream_with_context
import fitz
import io
import base64
import uuid
import os
import difflib
import json
from config import UPLOAD_FOLDER, OUTPUT_FOLDER

api_bp = Blueprint('api', __name__)


@api_bp.route('/page_preview', methods=['POST'])
def page_preview():
    """
    Returns a PNG preview of a specific PDF page as base64.
    
    Request:
        pdf_file (file): The PDF file.
        pagina (int): Page number (base 1).
    
    Response:
        JSON with {image: "data:image/png;base64,..."}
    """
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No se ha seleccionado un archivo'}), 400
    
    file = request.files['pdf_file']
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Por favor, suba un archivo PDF'}), 400
    
    try:
        pagina = int(request.form.get('pagina', 1))
    except ValueError:
        return jsonify({'error': 'El número de página debe ser un entero'}), 400
    
    pdf_bytes = file.read()
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    except Exception:
        return jsonify({'error': 'No se pudo abrir el PDF'}), 400
    
    if pagina < 1 or pagina > doc.page_count:
        doc.close()
        return jsonify({'error': f'Página fuera de rango (1-{doc.page_count})'}), 400
    
    page = doc[pagina - 1]
    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    img_bytes = pix.tobytes('png')
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    
    doc.close()
    
    return jsonify({'image': f'data:image/png;base64,{img_b64}'})


@api_bp.route('/save_signature', methods=['POST'])
def save_signature():
    """
    Saves a signature image from base64 to a temp file.
    
    Request:
        JSON { signature_base64: "data:image/png;base64,..." }
    
    Response:
        JSON { filename: "firma_temp_abc123.png" }
    """
    data = request.get_json()
    if not data or 'signature_base64' not in data:
        return jsonify({'error': 'No se recibió la firma'}), 400
    
    base64_data = data['signature_base64']
    if ',' in base64_data:
        base64_data = base64_data.split(',')[1]
    
    try:
        img_bytes = base64.b64decode(base64_data)
    except Exception:
        return jsonify({'error': 'Base64 inválido'}), 400
    
    filename = f'firma_temp_{uuid.uuid4().hex[:8]}.png'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    with open(filepath, 'wb') as f:
        f.write(img_bytes)
    
    return jsonify({'filename': filename})


@api_bp.route('/thumbnails', methods=['POST'])
def thumbnails():
    """
    Returns thumbnails for all pages of a PDF as base64 array.
    
    Request:
        pdf_file (file): The PDF file.
        dpi (int): Thumbnail resolution. Default: 72.
    
    Response:
        JSON { thumbnails: ["data:image/png;base64,...", ...] }
    """
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No se ha seleccionado un archivo'}), 400
    
    file = request.files['pdf_file']
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Por favor, suba un archivo PDF'}), 400
    
    try:
        dpi = int(request.form.get('dpi', 72))
    except ValueError:
        dpi = 72
    
    pdf_bytes = file.read()
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    except Exception:
        return jsonify({'error': 'No se pudo abrir el PDF'}), 400
    
    result = []
    for page in doc:
        pixmap = page.get_pixmap(dpi=dpi)
        img_bytes = pixmap.tobytes('png')
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        result.append(f'data:image/png;base64,{img_b64}')
    
    doc.close()
    
    return jsonify({'thumbnails': result})


@api_bp.route('/page_preview_by_name', methods=['POST'])
def page_preview_by_name():
    """
    Returns a PNG preview of a specific PDF page by filename.
    
    Request:
        pdf_nombre (str): Name of the PDF file in UPLOAD_FOLDER.
        pagina (int): Page number (base 1).
    
    Response:
        JSON with {image: "data:image/png;base64,..."}
    """
    from config import UPLOAD_FOLDER
    
    pdf_nombre = request.form.get('pdf_nombre', '')
    if not pdf_nombre:
        return jsonify({'error': 'No se proporcionó el nombre del archivo'}), 400
    
    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_nombre)
    if not os.path.exists(pdf_path):
        return jsonify({'error': 'Archivo no encontrado'}), 400
    
    try:
        pagina = int(request.form.get('pagina', 1))
    except ValueError:
        return jsonify({'error': 'El número de página debe ser un entero'}), 400
    
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return jsonify({'error': 'No se pudo abrir el PDF'}), 400
    
    if pagina < 1 or pagina > doc.page_count:
        doc.close()
        return jsonify({'error': f'Página fuera de rango (1-{doc.page_count})'}), 400
    
    page = doc[pagina - 1]
    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    img_bytes = pix.tobytes('png')
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    
    doc.close()
    
    return jsonify({'image': f'data:image/png;base64,{img_b64}'})


@api_bp.route('/compare', methods=['POST'])
def compare_pdfs():
    """Compara dos PDFs y devuelve HTML de diferencias como JSON."""
    if 'pdf_file_1' not in request.files or 'pdf_file_2' not in request.files:
        return jsonify({'error': 'Sube los dos archivos PDF'}), 400

    file1 = request.files['pdf_file_1']
    file2 = request.files['pdf_file_2']

    if not (file1.filename.endswith('.pdf') and file2.filename.endswith('.pdf')):
        return jsonify({'error': 'Ambos deben ser archivos PDF'}), 400

    pdf_path_1 = os.path.join(UPLOAD_FOLDER, 'c1_' + file1.filename)
    pdf_path_2 = os.path.join(UPLOAD_FOLDER, 'c2_' + file2.filename)
    file1.save(pdf_path_1)
    file2.save(pdf_path_2)

    try:
        doc1, doc2 = fitz.open(pdf_path_1), fitz.open(pdf_path_2)
        texto1 = [line for page in doc1 for line in page.get_text().splitlines()]
        texto2 = [line for page in doc2 for line in page.get_text().splitlines()]
        doc1.close()
        doc2.close()

        differ = difflib.HtmlDiff(wrapcolumn=80)
        tabla = differ.make_table(texto1, texto2, file1.filename, file2.filename, True, 3)

        html = f"""<style>
.diff_add{background:#d1fae5}.diff_sub{background:#fee2e2}.diff_chg{background:#fef9c3}
.diff_header{background:#f3f4f6;font-weight:bold}table.diff{width:100%;font-size:13px;border-collapse:collapse}
td{padding:4px 8px;vertical-align:top}</style>{tabla}"""

        return jsonify({'html': html, 'file1': file1.filename, 'file2': file2.filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/ocr/upload', methods=['POST'])
def ocr_upload():
    """Sube el PDF y retorna información sin procesarlo."""
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No se ha seleccionado un archivo'}), 400
    
    file = request.files['pdf_file']
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Debe ser un archivo PDF'}), 400
    
    filename = 'ocr_' + str(uuid.uuid4().hex[:8]) + '_' + file.filename
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        doc.close()
        return jsonify({'filename': filename, 'total_pages': total_pages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/ocr/stream/', methods=['GET'])
def ocr_stream(filename):
    """Stream de OCR por SSE."""
    from PIL import Image
    import pytesseract
    
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(pdf_path):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    
    def generate():
        try:
            doc = fitz.open(pdf_path)
            total = doc.page_count
            
            for i, page in enumerate(doc):
                pixmap = page.get_pixmap(dpi=300)
                imagen = Image.open(io.BytesIO(pixmap.tobytes("png")))
                texto = pytesseract.image_to_string(imagen, lang='spa')
                
                done = (i == total - 1)
                data = json.dumps({
                    'page': i + 1,
                    'total': total,
                    'text': texto,
                    'done': done
                })
                yield f"data: {data}\n\n"
            
            doc.close()
        except Exception as e:
            error_data = json.dumps({'error': str(e)})
            yield f"data: {error_data}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )