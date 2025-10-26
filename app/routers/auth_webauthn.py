# app/routers/auth_webauthn.py
from __future__ import annotations

import base64
from typing import Any, Dict, List, Mapping, Protocol, cast

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session, select

from fido2.server import Fido2Server
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    UserVerificationRequirement,
)
from fido2.cose import CoseKey
from fido2 import cbor

from app.db import get_session
from app.models_auth import User, WebAuthnCredential
from app.security import verify_jwt, issue_jwt
from app.config import settings

router = APIRouter(prefix="/auth/webauthn", tags=["auth"])

_rp = PublicKeyCredentialRpEntity(id=settings.RP_ID, name=settings.RP_NAME)
_server = Fido2Server(_rp)

# simpelt "state" lager (brug Redis/DB i prod)
_pending: Dict[str, Any] = {}

USER_ID_MISSING = "User has no id"

# ----- typing shims ---------------------------------------------------------


class AttestedLike(Protocol):
    """Minimal shape used by FIDO2 authenticate_complete in v1.x."""
    aaguid: bytes
    credential_id: bytes
    public_key: CoseKey


class _AttCred:
    """Small runtime object satisfying the attributes FIDO2 reads."""
    __slots__ = ("aaguid", "credential_id", "public_key")

    def __init__(self, aaguid: bytes, credential_id: bytes, public_key: CoseKey) -> None:
        self.aaguid = aaguid
        self.credential_id = credential_id
        self.public_key = public_key


# ----- helpers --------------------------------------------------------------

def _b64url_encode(b: bytes) -> str:
    # Input SKAL være bytes; returnerer str uden padding.
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    # Dekoder urlsafe b64 (med eller uden padding) til bytes.
    # Nogle type checkere (pyright) markerer '+' mellem LiteralString og str som usikkert.
    # Ved at widen'e til en almindelig str først undgår vi fejlen.
    pad = "=" * (-len(s) % 4)
    s_str: str = s  # widen LiteralString -> str
    return base64.urlsafe_b64decode(s_str + pad)


def _auth_tmp(token: str, session: Session) -> User:
    try:
        claims = verify_jwt(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid tmp token")
    if not claims.get("stepup"):
        raise HTTPException(status_code=401, detail="Token is not step-up")
    uid = int(claims["sub"])
    user = session.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not active")
    return user


def _allowed_descriptors(session: Session, user_id: int) -> List[PublicKeyCredentialDescriptor]:
    rows = session.exec(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)
    ).all()
    return [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=_b64url_decode(r.credential_id_b64),
        )
        for r in rows
    ]


def _registered_credentials(session: Session, user_id: int) -> List[AttestedLike]:
    """
    Vi gemmer public_key som urlsafe-b64 af COSE (CBOR) bytes. Her:
      1) b64-dekoder -> bytes
      2) cbor.decode(bytes) -> Mapping[int, Any] (COSE map)
      3) CoseKey.parse(mapping) -> CoseKey
    Returnerer en liste af _AttCred-objekter med de felter FIDO2 bruger.
    """
    rows = session.exec(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)
    ).all()

    creds: List[AttestedLike] = []
    for r in rows:
        cred_id: bytes = _b64url_decode(r.credential_id_b64)
        pk_b64 = r.public_key_b64
        if not pk_b64:
            # uden public key kan vi ikke verificere
            continue

        pk_bytes: bytes = _b64url_decode(pk_b64)
        pk_cose_any = cbor.decode(pk_bytes)
        pk_cose = cast(Mapping[int, Any], pk_cose_any)
        cose_key: CoseKey = CoseKey.parse(pk_cose)

        aaguid = b"\x00" * 16
        creds.append(_AttCred(aaguid, cred_id, cose_key))
    return creds


# ----- routes: register -----------------------------------------------------

@router.post("/register/options")
def register_options(
    tmp_token: str = Body(...),
    session: Session = Depends(get_session),
):
    user = _auth_tmp(tmp_token, session)
    if user.id is None:
        raise HTTPException(status_code=500, detail=USER_ID_MISSING)
    uid: int = cast(int, user.id)

    user_entity = PublicKeyCredentialUserEntity(
        id=str(uid).encode("utf-8"),
        name=user.email,
        display_name=user.email,
    )

    exclude = _allowed_descriptors(session, uid)

    options, state = _server.register_begin(
        user=user_entity,
        credentials=exclude,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _pending[f"reg:{uid}"] = state
    return options


@router.post("/register/verify")
def register_verify(
    tmp_token: str = Body(...),
    client_response: dict = Body(...),
    session: Session = Depends(get_session),
):
    user = _auth_tmp(tmp_token, session)
    if user.id is None:
        raise HTTPException(status_code=500, detail=USER_ID_MISSING)
    uid: int = cast(int, user.id)

    state = _pending.pop(f"reg:{uid}", None)
    if not state:
        raise HTTPException(status_code=400, detail="No pending registration")

    # fido2 v1.x: giv hele browser-svaret som response=
    try:
        result = _server.register_complete(
            state=state, response=client_response
        )
    except Exception as ex:
        raise HTTPException(
            status_code=400, detail=f"WebAuthn register failed: {ex}")

    # credential id: brug klientens rawId hvis muligt
    try:
        cred_id_bytes = _b64url_decode(client_response["rawId"])
    except Exception:
        cd = getattr(result, "credential_data", None)
        cred_id_bytes = getattr(cd, "credential_id", None)
        if isinstance(cred_id_bytes, bytearray):
            cred_id_bytes = bytes(cred_id_bytes)
        if not isinstance(cred_id_bytes, bytes):
            raise HTTPException(
                status_code=400, detail="Could not extract credential id")

    # public key (rå COSE/CBOR) + sign_count
    cd = getattr(result, "credential_data", None)
    pubkey_bytes = getattr(cd, "public_key", b"")
    if isinstance(pubkey_bytes, bytearray):
        pubkey_bytes = bytes(pubkey_bytes)
    elif not isinstance(pubkey_bytes, bytes):
        pubkey_bytes = b""

    sign_count = getattr(result, "sign_count", 0)
    if not isinstance(sign_count, int):
        sign_count = 0

    cred_id_b64 = _b64url_encode(cred_id_bytes)
    pubkey_b64 = _b64url_encode(pubkey_bytes) if pubkey_bytes else ""

    session.add(
        WebAuthnCredential(
            user_id=uid,
            credential_id_b64=cred_id_b64,
            public_key_b64=pubkey_b64,
            sign_count=sign_count,
            transports_json=None,
        )
    )
    user.webauthn_enabled = True
    session.add(user)
    session.commit()
    return {"status": "ok"}


# ----- routes: authenticate -------------------------------------------------

@router.post("/authenticate/options")
def authenticate_options(
    tmp_token: str = Body(...),
    session: Session = Depends(get_session),
):
    user = _auth_tmp(tmp_token, session)
    if user.id is None:
        raise HTTPException(status_code=500, detail=USER_ID_MISSING)
    uid: int = cast(int, user.id)

    allowed = _allowed_descriptors(session, uid)
    if not allowed:
        raise HTTPException(status_code=404, detail="No passkeys registered")

    options, state = _server.authenticate_begin(
        credentials=allowed,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _pending[f"auth:{uid}"] = state
    return options


@router.post("/authenticate/verify")
def authenticate_verify(
    tmp_token: str = Body(...),
    client_response: dict = Body(...),
    session: Session = Depends(get_session),
):
    user = _auth_tmp(tmp_token, session)
    if user.id is None:
        raise HTTPException(status_code=500, detail=USER_ID_MISSING)
    uid: int = cast(int, user.id)

    state = _pending.pop(f"auth:{uid}", None)
    if not state:
        raise HTTPException(
            status_code=400, detail="No pending authentication")

    creds_for_verify: List[AttestedLike] = _registered_credentials(
        session, uid)

    try:
        # cast(...) to satisfy the type checker; runtime only needs the attributes
        result = _server.authenticate_complete(
            state=state,
            credentials=cast(Any, creds_for_verify),
            response=client_response,
        )
    except Exception as ex:
        raise HTTPException(
            status_code=400, detail=f"WebAuthn authenticate failed: {ex}")

    # (valgfrit) opdater sign_count for credentialen
    try:
        raw_id_bytes = _b64url_decode(client_response["rawId"])
        cred_id_b64 = _b64url_encode(raw_id_bytes)
        row = session.exec(
            select(WebAuthnCredential).where(
                WebAuthnCredential.credential_id_b64 == cred_id_b64
            )
        ).first()
        new_sc = getattr(result, "new_sign_count", None)
        if row is not None and isinstance(new_sc, int):
            row.sign_count = new_sc
            session.add(row)
            session.commit()
    except Exception:
        pass

    full = issue_jwt(str(uid), extra={"amr": ["pwd", "webauthn"]})
    return {"token": full}
