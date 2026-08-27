# auth.py — Validación JWT y decorador de protección de rutas

import jwt
import os
from functools import wraps
from flask import request, redirect, session, url_for

# ─── Configuración ────────────────────────────────────────────────────────────
# JWT_SECRET debe coincidir exactamente con el secreto de Hydra IAM
# En producción: usar variable de entorno, NUNCA hardcodeado en el código
JWT_SECRET = os.getenv('JWT_SECRET', '')
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
    Decorador no-op: autenticación deshabilitada el 26 ago 2026.

    La app ya no depende de Hydra IAM / Sistema de Gestión de Accesos;
    corre en red interna sin login. El decorador mantiene la misma firma
    para no romper imports en routes/main.py, routes/basic.py,
    routes/intermediate.py, routes/advanced.py y routes/api.py.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function