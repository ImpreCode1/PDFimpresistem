# routes/main.py — Blueprint: main

from flask import Blueprint, request, render_template, send_from_directory, redirect, url_for, session
from utils import limpiar_carpeta
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from werkzeug.utils import secure_filename
from pdf2docx import Converter
from auth import login_required, HYDRA_LOGIN_URL, validar_token, JWT_SECRET
import jwt
import os
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)


# ─── Ruta de autenticación SSO ────────────────────────────────────────────────
@main_bp.route('/auth')
def auth():
    """
    Punto de entrada del flujo SSO con Hydra IAM.

    Hydra redirige aquí tras login exitoso con el JWT en la URL:
        GET /auth?token=eyJhbGciOiJIUzI1NiJ9...

    Flujo:
        1. Extrae token del parámetro URL
        2. Valida firma, issuer, audience y expiración
        3. Guarda datos del usuario en la sesión Flask
        4. Redirige al inicio SIN el token en la URL
        5. Si hay error → redirige a Hydra para nuevo token
    """
    token = request.args.get('token')

    # Modo desarrollo: auto-generar token si no existe
    if not token:
        if os.getenv('FLASK_ENV') == 'development' or os.getenv('DEBUG') == '1':
            payload = {
                'sub': 'dev-user',
                'email': 'dev@impresistem.com',
                'name': 'Desarrollador',
                'roles': ['admin'],
                'positionId': '1',
                'platform': 'pdf',
                'iss': 'hydra-iam',
                'aud': 'internal-platforms',
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(minutes=15)
            }
            token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
        else:
            return redirect(HYDRA_LOGIN_URL)

    try:
        payload = validar_token(token)

        session['user'] = {
            'sub': payload['sub'],
            'email': payload['email'],
            'name': payload['name'],
            'roles': payload['roles'],
            'positionId': payload.get('positionId'),
            'platform': payload.get('platform'),
        }
        session.permanent = True

        return redirect(url_for('main.index'))

    except jwt.ExpiredSignatureError:
        return redirect(HYDRA_LOGIN_URL)

    except jwt.InvalidIssuerError:
        return 'Token de emisor no autorizado.', 403

    except jwt.InvalidAudienceError:
        return 'Token no autorizado para esta plataforma.', 403

    except jwt.InvalidSignatureError:
        return 'Token con firma inválida.', 403

    except jwt.DecodeError:
        return 'Token malformado.', 400

    except Exception as e:
        print(f'[Auth] Error inesperado validando token: {e}')
        return redirect(HYDRA_LOGIN_URL)


# ─── Cierre de sesión SSO ─────────────────────────────────────────────────────
@main_bp.route('/logout', methods=['POST'])
def logout():
    """Cierra la sesión local y redirige a Hydra."""
    session.clear()
    return redirect(HYDRA_LOGIN_URL)


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