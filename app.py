# app.py — slim version after refactor

from flask import Flask
import os
from datetime import timedelta
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

# JWT_SECRET se valida al inicio para fallo rápido si no está definida.
# Se lee de variable de entorno sin fallback, igual que SECRET_KEY.
_jwt_secret = os.environ.get('JWT_SECRET')
if not _jwt_secret:
    raise RuntimeError(
        'JWT_SECRET no está definida. Configúrala en el entorno (variable '
        'JWT_SECRET) antes de iniciar la aplicación.'
    )

# SESSION_COOKIE_SECURE se activa solo en producción (HTTPS). En desarrollo
# local (FLASK_ENV != production) se desactiva para permitir HTTP.
es_produccion = os.getenv('FLASK_ENV') == 'production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['SESSION_PERMANENT'] = True
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30 MB
app.config['SESSION_COOKIE_NAME'] = 'pdf_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = es_produccion
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_DOMAIN'] = False  # Allow cookies for current domain

# Flask-Limiter: límites por defecto para todas las rutas. Las rutas de
# conversión procesan archivos grandes y consumen CPU/IO, por lo que el
# límite diario y por hora protege el servidor de abuso o uso excesivo.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=['200 per day', '50 per hour'],
)


@app.after_request
def add_security_headers(response):
    """
    Añade headers de seguridad base a todas las respuestas.

    Args:
        response (Response): Objeto response de Flask.

    Returns:
        Response: Objeto response con headers de seguridad añadidos.
    """
    # CSP: restringe fuentes de scripts, estilos, imágenes y conexiones.
    # Se permiten los CDN usados por las plantillas (tailwind, pdf-lib,
    # jszip, sortablejs) tanto en script como en style.
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; "
        "font-src 'self' data:; "
        "connect-src 'self'"
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
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

# Scheduler (unchanged)
zona_colombia = pytz.timezone('America/Bogota')
scheduler = BackgroundScheduler(timezone=zona_colombia)
scheduler.add_job(
    limpiar_archivos_programada,
    CronTrigger(hour=19, minute=0, timezone=zona_colombia)
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))

application = app  # mod_wsgi

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080, debug=True)