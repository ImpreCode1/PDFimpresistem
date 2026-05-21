# routes/api.py — Blueprint: api

from flask import Blueprint, request, jsonify, Response, stream_with_context
from auth import login_required
import fitz
import io
import base64
import uuid
import os
import difflib
import json
from config import UPLOAD_FOLDER, OUTPUT_FOLDER

api_bp = Blueprint('api', __name__)


# FIX HIGH: Add CORS headers for cross-origin requests from interactive views
@api_bp.after_request
def add_cors_headers(response):
    """
    Añade headers CORS para solicitudes de origen cruzado.

    Args:
        response (Response): Objeto response de Flask.

    Returns:
        Response: Objeto response con headers CORS añadidos.
    """
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@api_bp.route('/page_preview', methods=['POST', 'OPTIONS'])
@login_required
def page_preview():
    """
    Retorna una vista previa PNG de una página específica del PDF en base64.

    Args:
        pdf_file (file): Archivo PDF enviado en el request.
        pagina (int): Número de página (base 1). Por defecto: 1.

    Returns:
        JSON: {'image': 'data:image/png;base64,...'}

    Raises:
        400: Si no se selecciona archivo o página fuera de rango.
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
    except Exception as e:
        return jsonify({'error': f'No se pudo abrir el PDF: {str(e)}'}), 400
    
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


@api_bp.route('/save_signature', methods=['POST', 'OPTIONS'])
@login_required
def save_signature():
    """
    Guarda una imagen de firma desde base64 en un archivo temporal.

    Args:
        signature_base64 (str): Imagen en formato data URL base64.

    Returns:
        JSON: {'filename': 'firma_temp_abc123.png'}

    Raises:
        400: Si no se recibe la firma o el base64 es inválido.
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


@api_bp.route('/thumbnails', methods=['POST', 'OPTIONS'])
@login_required
def thumbnails():
    """
    Retorna miniaturas de todas las páginas de un PDF como array base64.

    Args:
        pdf_file (file): Archivo PDF enviado en el request.
        dpi (int): Resolución de las miniaturas. Por defecto: 72.

    Returns:
        JSON: {'thumbnails': ['data:image/png;base64,...', ...]}

    Raises:
        400: Si no se selecciona archivo.
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


@api_bp.route('/page_preview_by_name', methods=['POST', 'OPTIONS'])
@login_required
def page_preview_by_name():
    """
    Retorna una vista previa PNG de una página específica del PDF por nombre de archivo.

    Args:
        pdf_nombre (str): Nombre del archivo PDF en UPLOAD_FOLDER.
        pagina (int): Número de página (base 1). Por defecto: 1.

    Returns:
        JSON: {'image': 'data:image/png;base64,...'}

    Raises:
        400: Si no se proporciona nombre, archivo no existe o página fuera de rango.
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


