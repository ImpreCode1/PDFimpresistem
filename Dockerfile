# Dockerfile — PDFimpresistem
# Entorno adicional Docker (no reemplaza Apache/mod_wsgi de plattstest/producción).
# Ver app.wsgi y app.py:application para el despliegue actual en mod_wsgi.

# 1) Imagen base: python 3.12 slim (Debian mínimo, sin paquetes innecesarios)
FROM python:3.12-slim

# 2) Variables para mejor logging y evitar .pyc en contenedor
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 3) Directorio de trabajo dentro del contenedor
WORKDIR /app

# 4) Instalar dependencias del sistema mínimas para compilar/librerías
#    (libGL para opencv-headless no es necesario; se deja capa lista por si se requiere build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # build-essential se necesita solo si algún wheel no está disponible; se deja opcional
    # build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5) Copiar solo requirements primero para aprovechar cache de Docker
COPY requirements.txt .

# 6) Instalar dependencias de Python + gunicorn (servidor WSGI para el contenedor)
#    bottleneck y numexpr ya están en requirements.txt — no se duplican
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn==23.0.0

# 7) Copiar el resto del código (respetando .dockerignore; .env NO se copia)
COPY . .

# 8) Crear carpetas de persistencia si no existen (también se montan como volúmenes)
RUN mkdir -p /app/uploads /app/outputs

# 9) Exponer puerto de la app (gunicorn escuchará aquí)
EXPOSE 8000

# 10) Variables por defecto (se sobreescriben con env_file .env externo en docker-compose)
ENV FLASK_ENV=production

# 11) Comando por defecto: gunicorn como WSGI (independiente de Apache/mod_wsgi)
#     --workers 2, timeout 120s por PDFs grandes/conversiones
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "app:app"]
