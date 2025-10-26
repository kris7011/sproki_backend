# app/models_auth.py
from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: Optional[str] = None        # None if passkey-only
    is_active: bool = True
    # 2FA flags
    totp_enabled: bool = False
    webauthn_enabled: bool = False
    # bookkeeping
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserTOTP(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    secret: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WebAuthnCredential(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    credential_id_b64: str = Field(index=True, unique=True)
    public_key_b64: str
    sign_count: int = 0
    transports_json: Optional[dict] = Field(
        default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
