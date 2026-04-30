# auth.py — Validación JWT y decorador de protección de rutas

import jwt
import os
from functools import wraps
from flask import request, redirect, session, url_for

# ─── Configuración ────────────────────────────────────────────────────────────
# JWT_SECRET debe coincidir exactamente con el secreto de Hydra IAM
# En producción: usar variable de entorno, NUNCA hardcodeado en el código
JWT_SECRET = os.getenv('JWT_SECRET', 'super_secret_key')
if not os.getenv('JWT_SECRET'):
    import warnings
    warnings.warn(
        "[auth] JWT_SECRET no está en variables de entorno. "
        "Usando valor por defecto — NO apto para producción.",
        stacklevel=1
    )
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

    Si no hay sesión → forzar re-autenticación en Hydra.
    Si hay sesión → deja pasar la petición y la información del usuario
    queda disponible en session['user'] dentro de la ruta.

    También acepta token desde URL o header Authorization como fallback.

    Uso:
        @main_bp.route('/')
        @login_required
        def index():
            user = session['user']  # {'sub': ..., 'email': ..., 'name': ..., 'roles': [...]}
            return render_template('index.html')
"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Verificar sesión primero
        if 'user' in session:
            print(f'[login_required] Session found: {session.get("user", {})}')
            return f(*args, **kwargs)

        # 2. Fallback: verificar token desde URL
        token = request.args.get('token')
        if token:
            print(f'[login_required] Token found in URL, validating...')
            try:
                payload = validar_token(token)
                print(f'[login_required] Token valid, payload: {payload.get("email")}')
                session['user'] = {
                    'sub': payload['sub'],
                    'email': payload['email'],
                    'name': payload['name'],
                    'roles': payload['roles'],
                    'positionId': payload.get('positionId'),
                    'platform': payload.get('platform'),
                }
                session.permanent = True
                print(f'[login_required] Session saved, redirecting to index')
                return redirect(url_for('main.index'))
            except Exception as e:
                print(f'[login_required] Token validation failed: {type(e).__name__}: {e}')
                pass

        # 3. Fallback: verificar token desde header Authorization
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
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
                return f(*args, **kwargs)
            except Exception as e:
                print(f'[login_required] Token validation failed: {type(e).__name__}: {e}')
                pass

        # No hay sesión ni token válido → redirigir a Hydra
        print('[login_required] No session, redirecting to HYDRA_LOGIN_URL')
        return redirect(HYDRA_LOGIN_URL)
    return decorated_function