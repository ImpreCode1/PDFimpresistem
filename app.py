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
import pytz
import atexit

app = Flask(__name__)
# FIX HIGH: Missing SECRET_KEY causes session inconsistencies across environments
app.secret_key = os.getenv('SECRET_KEY', 'PDFimpresistem-dev-key-2024')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['SESSION_PERMANENT'] = True
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30 MB

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(basic_bp)
app.register_blueprint(intermediate_bp)
app.register_blueprint(advanced_bp)
app.register_blueprint(api_bp, url_prefix='/api')

@app.errorhandler(413)
def archivo_demasiado_grande(e):
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