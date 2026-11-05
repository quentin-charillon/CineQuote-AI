from fastapi import APIRouter, Depends, Request, Response, status
from fastapi import HTTPException

from app.config import get_settings
from app.models.account import User
from app.schemas.account import LoginRequest, RegisterRequest, UserResponse
from app.services.auth import (
    AccountConflictError, InvalidCredentialsError, auth_service, get_current_user,
)
from app.services.security import security_limiters

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.auth_cookie_name, token, max_age=settings.auth_session_days * 86400,
        httponly=True, secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite, path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response) -> User:
    security_limiters.check_registration(request)
    try:
        user, token = auth_service.register(payload.email, payload.username, payload.password)
    except AccountConflictError as error:
        raise HTTPException(status_code=409, detail="Unable to create an account with these details") from error
    _set_cookie(response, token)
    return user


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> User:
    security_limiters.check_login(request, payload.email)
    try:
        user, token = auth_service.login(payload.email, payload.password)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="Invalid email or password") from error
    _set_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    settings = get_settings()
    auth_service.logout(request.cookies.get(settings.auth_cookie_name))
    response.delete_cookie(settings.auth_cookie_name, path="/")


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
