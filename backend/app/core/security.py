"""Briques de sécurité : mots de passe, jetons d'accès et de renouvellement.

Deux jetons, deux rôles :
- le jeton d'ACCÈS (JWT, 15 min) accompagne chaque requête dans l'en-tête
  « Authorization: Bearer … ». Le serveur le vérifie sans consulter la base ;
- le jeton de RENOUVELLEMENT (aléatoire, 30 jours) est rangé dans un cookie
  « httpOnly », illisible par JavaScript (donc à l'abri d'une faille XSS).
  Il sert uniquement à obtenir un nouveau jeton d'accès.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

JWT_ALGORITHM = "HS256"

# Argon2id : algorithme recommandé par l'OWASP. Il est volontairement lent et
# gourmand en mémoire, ce qui rend le cassage des mots de passe très coûteux.
_password_hasher = PasswordHash.recommended()

# Empreinte factice utilisée quand l'e-mail n'existe pas : on effectue quand
# même un calcul Argon2, pour que le temps de réponse ne révèle pas si un
# compte existe (attaque « par mesure du temps »).
_DUMMY_HASH = _password_hasher.hash("mot-de-passe-factice-pour-egaliser-le-temps")


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _password_hasher.verify(password, _DUMMY_HASH)
        return False
    return _password_hasher.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),  # « subject » : à qui appartient le jeton
        "type": "access",
        "iat": now,  # « issued at » : date d'émission
        "exp": now + timedelta(minutes=settings.access_token_minutes),  # expiration
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Renvoie l'identifiant de l'utilisateur, ou None si le jeton est invalide,
    falsifié ou expiré."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload["sub"])
    except (KeyError, ValueError):
        return None


def generate_refresh_token() -> str:
    """Jeton aléatoire de 256 bits, impossible à deviner."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Seule l'empreinte SHA-256 est stockée en base : une fuite de la base ne
    permettrait pas de réutiliser les jetons. (Argon2 est inutile ici : le
    jeton est déjà totalement aléatoire, contrairement à un mot de passe.)"""
    return hashlib.sha256(token.encode()).hexdigest()
