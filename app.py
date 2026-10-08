# app.py — slim version after refactor

from flask import Flask, request, jsonify
import os
import tempfile
from datetime import timedelta
import fitz
from config import UPLOAD_FOLDER, OUTPUT_FOLDER
from utils import limpiar_archivos_programada
from routes.main import main_bp
from routes.basic import basic_bp
from routes.intermediate import intermediate_bp
from routes.advanced import advanced_bp
from routes.api import api_bp
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
import pytz
import atexit

app = Flask(__name__)

# SECRET_KEY debe leerse de la variable de entorno. Sin fallback hardcoded:
# si no está definida, se lanza un error explícito en lugar de usar una clave
# predecible que pondría en riesgo las sesiones.
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    raise RuntimeError(
        'SECRET_KEY no está definida. Configúrala en el entorno (variable '
        'SECRET_KEY) antes de iniciar la aplicación.'
    )
app.secret_key = _secret_key

# CSRF: protege todos los endpoints POST (enviado como hidden input en los
# forms nativos y como header X-CSRFToken en las llamadas fetch).
csrf = CSRFProtect(app)

# JWT_SECRET se valida al inicio para fallo rápido si no está definida.
# Se lee de variable de entorno sin fallback, igual que SECRET_KEY.
_jwt_secret = os.environ.get('JWT_SECRET')
if not _jwt_secret:
    raise RuntimeError(
        'JWT_SECRET no está definida. Configúrala en el entorno (variable '
        'JWT_SECRET) antes de iniciar la aplicación.'
    )

# SESSION_COOKIE_SECURE se desactiva (False) para permitir la app por HTTP.
# La sesión dura 8 h (una jornada). Antes eran 15 minutos: si el usuario
# tardaba en rellenar un formulario, el POST llegaba sin sesión y fallaba
# con "CSRF session token is missing" (o un 401 silencioso en /api, que el
# usuario percibía como que la herramienta "no hacía nada"). Con
# SESSION_REFRESH_EACH_REQUEST la cookie se renueva en cada petición, así
# que la sesión solo expira por inactividad real.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30 MB
app.config['SESSION_COOKIE_NAME'] = 'pdf_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_DOMAIN'] = False  # Allow cookies for current domain

# MuPDF registra un error por objeto cuando un PDF tiene el "structure tree"
# corrupto (p. ej. "No common ancestor in structure tree"). pdf2docx y las
# vistas previas lo disparan en PDFs mal formados y llegan a inundar el
# error.log de Apache (cientos de líneas por documento). No afecta al
# resultado, así que se silencia para no perder de vista los errores reales.
try:
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
except Exception:
    pass

# Talisman: políticas de seguridad por headers (CSP incluido). Los scripts
# inline de las plantillas usan nonce ({{ csp_nonce() }}) y las librerías JS
# se sirven desde /static/js/vendor/, así que script-src queda en 'self'.
#
# 'script-src-attr': 'none' prohíbe explícitamente los atributos de evento
# inline (onclick, onchange...). Ninguna plantilla los usa ya; la directiva
# existe para que reintroducir uno falle de forma ruidosa en lugar de depender
# solo de la ausencia de 'unsafe-inline' en script-src.
#
# 'worker-src': pdf.js lanza un Web Worker (ver unir.html). Sin esta directiva
# la resolución cae en script-src, así que al quitar los CDN del allowlist el
# worker dejaría de cargar y las miniaturas se renderizarían en blanco: el
# fallo se traga un catch y no se ve como error.
#
# style-src mantiene 'unsafe-inline': lo autorizan los bloques <style> de las
# plantillas y los atributos style="" (252 de ellos solo en index.html). Es
# independiente de script-src y no habilita ejecución de JS.
csp = {
    'default-src': "'self'",
    'img-src': ["'self'", 'data:', 'https:'],
    'script-src': ["'self'"],
    'script-src-attr': ["'none'"],
    'worker-src': ["'self'", 'blob:'],
    'style-src': ["'self'", "'unsafe-inline'", 'cdn.jsdelivr.net', 'fonts.googleapis.com'],
    'font-src': ['fonts.gstatic.com'],
}
Talisman(
    app,
    content_security_policy=csp,
    content_security_policy_nonce_in=['script-src'],
    force_https=False,
    session_cookie_secure=False,
)

# Flask-Limiter: límites por defecto para todas las rutas. Las rutas de
# conversión procesan archivos grandes y consumen CPU/IO, por lo que el
# límite diario y por hora protege el servidor de abuso o uso excesivo.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=['200 per day', '50 per hour'],
)


@app.after_request
def add_no_cache_headers(response):
    """Evita el caché en respuestas POST y en descargas de archivos."""
    if request.method == 'POST' or request.path.startswith('/download/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
    return response


# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(basic_bp)
app.register_blueprint(intermediate_bp)
app.register_blueprint(advanced_bp)
app.register_blueprint(api_bp, url_prefix='/api')

@app.errorhandler(413)
def archivo_demasiado_grande(e):
    """Maneja el error 413 cuando el archivo excede el límite permitido.

    Se activa cuando el tamaño supera MAX_CONTENT_LENGTH (30 MB).

    Args:
        e: Excepción original de Flask/Werkzeug.

    Returns:
        tuple[str, int]: Mensaje de error y código HTTP 413.
    """
    return 'El archivo supera el límite de 30 MB. Por favor sube un archivo más pequeño.', 413


@app.errorhandler(CSRFError)
def manejar_csrf_error(e):
    """Da un mensaje claro cuando falta o caducó el token CSRF.

    Antes, un POST con la sesión caducada mostraba la página de error por
    defecto (o fallaba en silencio en /api) y el usuario lo interpretaba
    como "la herramienta no hace nada". Ahora /api responde JSON 400 y el
    resto muestra una página legible que invita a recargar.

    Args:
        e (CSRFError): Excepción de Flask-WTF.

    Returns:
        tuple: JSON 400 para /api, o página HTML 400 para el resto.
    """
    if request.path.startswith('/api'):
        return jsonify({
            'error': 'Sesión expirada o token de seguridad inválido. '
                     'Recarga la página y vuelve a intentarlo.'
        }), 400
    return (
        '<h1>Sesión expirada</h1>'
        '<p>Tu sesión caducó o la página estuvo abierta demasiado tiempo. '
        'Recarga el navegador o <a href="/">vuelve al inicio</a>.</p>'
    ), 400

# Scheduler: la limpieza programada de las 19:00 debe ejecutarse UNA sola vez.
# Con mod_wsgi en varios procesos (WSGIDaemonProcess processes=N), cada proceso
# importa este módulo y, sin control, arrancaría su propio BackgroundScheduler:
# la limpieza se ejecutaría N veces (borrados duplicados y errores de carrera).
# Se usa un candado de fichero (fcntl.flock) para que solo el primer proceso
# arranque el scheduler; los demás quedan sin él, que es justo lo que queremos.
scheduler = None
try:
    import fcntl
    _scheduler_lock = open(
        os.path.join(tempfile.gettempdir(), 'pdfimpresistem_scheduler.lock'), 'w'
    )
    fcntl.flock(_scheduler_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    zona_colombia = pytz.timezone('America/Bogota')
    scheduler = BackgroundScheduler(timezone=zona_colombia)
    scheduler.add_job(
        limpiar_archivos_programada,
        CronTrigger(hour=19, minute=0, timezone=zona_colombia)
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
except (ImportError, OSError):
    # ImportError: en Windows (dev) no existe fcntl. OSError: otro proceso ya
    # tiene el candado (lo normal cuando processes>1). En ambos casos este
    # proceso no arranca el scheduler.
    pass

application = app  # mod_wsgi

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080, debug=True)