# auth.py — Validación JWT y decorador de protección de rutas

import jwt
import os
from functools import wraps
from flask import request, redirect, session

# ─── Configuración ────────────────────────────────────────────────────────────
# JWT_SECRET debe coincidir exactamente con el secreto de Hydra IAM
# En producción: usar variable de entorno, NUNCA hardcodeado en el código
JWT_SECRET = os.getenv('JWT_SECRET', 'super_secret_key')
JWT_ALGORITHM = 'HS256'
JWT_ISSUER = 'hydra-iam'
JWT_AUDIENCE = 'internal-platforms'

# URL de login de Hydra — a donde se redirige si no hay sesión válida
HYDRA_LOGIN_URL = os.getenv('HYDRA_LOGIN_URL', 'https://central.impresistem.com/login')


# ─── Función de validación ────────────────────────────────────────────────────
def validar_token(token: str) -> dict:
    """
    Valida un JWT firmado por Hydra IAM.

    Verifica simultáneamente:
      - Firma con HS256 usando JWT_SECRET
      - Issuer: debe ser 'hydra-iam'
      - Audience: debe ser 'internal-platforms'
      - Expiración: rechaza tokens vencidos

    Args:
        token: String JWT recibido en la URL

    Returns:
        dict con el payload decodificado si el token es válido

    Raises:
        jwt.ExpiredSignatureError: Token vencido (exp < now)
        jwt.InvalidIssuerError: iss no es 'hydra-iam'
        jwt.InvalidAudienceError: aud no es 'internal-platforms'
        jwt.InvalidSignatureError: Firma manipulada o secreto incorrecto
        jwt.DecodeError: Token malformado (no es un JWT válido)
    """
    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],  # Lista explícita — previene ataques de algoritmo 'none'
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={
            'verify_exp': True,       # Siempre verificar expiración
            'verify_iss': True,       # Siempre verificar emisor
            'verify_aud': True,       # Siempre verificar audiencia
        }
    )
    return payload


# ─── Decorador de protección ──────────────────────────────────────────────────
def login_required(f):
    """
    Decorador que protege una ruta verificando que existe una sesión activa.

    Si no hay sesión → redirige a Hydra para que genere un nuevo token.
    Si hay sesión → deja pasar la petición y la información del usuario
    queda disponible en session['user'] dentro de la ruta.

    Uso:
        @main_bp.route('/')
        @login_required
        def index():
            user = session['user']  # {'sub': ..., 'email': ..., 'name': ..., 'roles': [...]}
            return render_template('index.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # No hay sesión activa → forzar re-autenticación en Hydra
            return redirect(HYDRA_LOGIN_URL)
        return f(*args, **kwargs)
    return decorated_function