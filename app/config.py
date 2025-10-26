# app/config.py
import os
from pydantic import BaseModel


class Settings(BaseModel):
    # crypto
    JWT_ISS: str = os.getenv("JWT_ISS", "sproki.local")
    JWT_AUD: str = os.getenv("JWT_AUD", "sproki.clients")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-change-me")
    JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))

    # WebAuthn (RP = relying party)
    RP_ID: str = os.getenv("RP_ID", "localhost")
    RP_NAME: str = os.getenv("RP_NAME", "Sproki")
    ORIGIN: str = os.getenv("ORIGIN", "http://localhost:3000")


settings = Settings()
