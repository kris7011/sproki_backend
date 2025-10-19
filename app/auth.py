# === FILE: app/auth.py
from fastapi import Depends, HTTPException, status

# Minimal stub. Integrate with your existing auth (JWT/MitID).


class User:
    def __init__(self, user_id: int, role: str):
        self.id = user_id
        self.role = role


def get_current_user() -> User:
    # Placeholder auth for development/testing. Replace with JWT or MitID verification.
    # This stub always returns a demo leader user.
    return User(user_id=1, role="leader")


def require_role(roles: list[str]):
    def _inner(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: required one of {roles}, got {user.role}"
            )
        return user
    return _inner
