"""Auth endpoints: /login, /me, /logout."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_user
from app.auth.passwords import verify_password
from app.auth.users import get_user_by_username

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    role: str


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request) -> UserOut:
    user = get_user_by_username(body.username)
    # Constant-ish-time: always run verify_password against either the real
    # hash or a dummy one, so a missing user looks like a wrong password from
    # the outside. (Not perfect; a real timing-attack defence needs more.)
    fallback_hash = "$2b$12$0000000000000000000000000000000000000000000000000000"
    ok = verify_password(body.password, user["password_hash"] if user else fallback_hash)
    if not user or not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    request.session["user_id"] = user["id"]
    return UserOut(id=user["id"], username=user["username"], role=user["role"])


@router.get("/me", response_model=UserOut)
def me(user: Annotated[dict, Depends(require_user)]) -> UserOut:
    return UserOut(id=user["id"], username=user["username"], role=user["role"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    request.session.clear()
