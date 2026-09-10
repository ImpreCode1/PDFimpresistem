import os
from flask import session, redirect, request, jsonify
from functools import wraps
import jwt

HYDRA_LOGIN_URL = "https://central.impresistem.com/login"


def validar_token(token: str) -> dict:
    """
    Decodifica y valida un JWT firmado por Hydra IAM.

    Args:
        token (str): Token JWT recibido como parámetro de URL.

    Returns:
        dict: Payload decodificado con sub, email, name, roles,
              positionId, platform, iat, exp, iss, aud.

    Raises:
        ValueError: Si el token es inválido, expirado, o no cumple
                    las restricciones de issuer/audience/algoritmo.
    """
    payload = jwt.decode(
        token,
        os.environ["JWT_SECRET"],
        algorithms=["HS256"],
        issuer="hydra-iam",
        audience="internal-platforms",
    )
    return payload


def login_required(f):
    """
    Decorador que exige sesión Flask activa.

    Deja pasar libremente las peticiones OPTIONS (preflight CORS).
    Para rutas bajo /api, responde JSON 401 si no hay sesión en vez
    de redirigir. Para el resto, redirige al login de Hydra Hub.

    Args:
        f (callable): Vista Flask a proteger.

    Returns:
        callable: Vista envuelta que verifica sesión antes de ejecutar.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return f(*args, **kwargs)
        if "user" not in session:
            if request.path.startswith("/api"):
                return jsonify({"error": "No autenticado"}), 401
            return redirect(HYDRA_LOGIN_URL)
        return f(*args, **kwargs)
    return decorated
