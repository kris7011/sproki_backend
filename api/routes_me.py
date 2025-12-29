# api/routes_me.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from .auth import get_current_user
from .models_user import User as UserModel

router = APIRouter(prefix="", tags=["me"])


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str


@router.get("/me", response_model=MeResponse)
async def me(user: UserModel = Depends(get_current_user)) -> UserModel:
    return user
