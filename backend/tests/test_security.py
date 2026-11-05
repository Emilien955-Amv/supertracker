"""Tests unitaires des briques de sécurité (aucun service externe requis)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import DEV_JWT_SECRET, Settings
from app.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_mot_de_passe_hache_puis_verifie() -> None:
    empreinte = hash_password("un-mot-de-passe-solide")

    assert empreinte != "un-mot-de-passe-solide"
    assert empreinte.startswith("$argon2id$")
    assert verify_password("un-mot-de-passe-solide", empreinte)
    assert not verify_password("mauvais-mot-de-passe", empreinte)


def test_verification_sans_compte_echoue_toujours() -> None:
    assert not verify_password("nimporte-quoi", None)


def test_jeton_acces_aller_retour() -> None:
    assert decode_access_token(create_access_token(42)) == 42


def test_jeton_falsifie_refuse() -> None:
    faux = jwt.encode(
        {"sub": "42", "type": "access"},
        "pas-la-bonne-cle-mais-assez-longue-pour-hs256",
        JWT_ALGORITHM,
    )
    assert decode_access_token(faux) is None


def test_jeton_expire_refuse() -> None:
    passe = datetime.now(UTC) - timedelta(minutes=1)
    expire = jwt.encode({"sub": "42", "type": "access", "exp": passe}, DEV_JWT_SECRET, "HS256")
    assert decode_access_token(expire) is None


def test_jeton_illisible_refuse() -> None:
    assert decode_access_token("ceci-n-est-pas-un-jeton") is None


def test_empreinte_jeton_renouvellement_stable() -> None:
    assert hash_refresh_token("abc") == hash_refresh_token("abc")
    assert len(hash_refresh_token("abc")) == 64


def test_production_refuse_le_secret_de_developpement() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret=DEV_JWT_SECRET, cookie_secure=True)


def test_production_exige_des_cookies_securises() -> None:
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(environment="production", jwt_secret="x" * 40, cookie_secure=False)
