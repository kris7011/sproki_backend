# app/routers/auth_dev.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.db import get_session
from app.models_auth import User
from app.security import issue_jwt

router = APIRouter(prefix="/auth/dev", tags=["auth"])


@router.get("/tmp-token")
def issue_tmp_token(user_id: int = Query(...), session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found/active")
    # amr: ["pwd"] + stepup flag
    token = issue_jwt(str(user.id), extra={"amr": ["pwd"], "stepup": True})
    return {"tmp_token": token}
