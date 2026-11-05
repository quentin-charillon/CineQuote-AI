import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import SessionLocal
from app.models.account import AuthSession, User


class AccountConflictError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class PasswordHasher:
    ITERATIONS = 600_000

    @classmethod
    def hash(cls, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, cls.ITERATIONS)
        return f"pbkdf2_sha256${cls.ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

    @staticmethod
    def verify(password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt, expected = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
            return hmac.compare_digest(actual, base64.b64decode(expected))
        except (ValueError, TypeError):
            return False


_DUMMY_PASSWORD_HASH = PasswordHasher.hash("timing-only-placeholder")


def _token_hash(token: str) -> str:
    secret = get_settings().session_secret
    if secret is None:
        # Backwards-compatible local development mode.
        return hashlib.sha256(token.encode()).hexdigest()
    return hmac.new(secret.get_secret_value().encode(), token.encode(), hashlib.sha256).hexdigest()


class AuthService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def register(self, email: str, username: str, password: str) -> tuple[User, str]:
        user = User(
            email=email.strip(), normalized_email=email.strip().casefold(),
            username=username.strip(), normalized_username=username.strip().casefold(),
            password_hash=PasswordHasher.hash(password),
        )
        with self._session_factory() as database:
            existing = database.scalar(select(User).where(or_(
                User.normalized_email == user.normalized_email,
                User.normalized_username == user.normalized_username,
            )))
            if existing:
                raise AccountConflictError
            database.add(user)
            try:
                database.flush()
                token = self._create_session(database, user.id)
                database.commit()
            except IntegrityError as error:
                database.rollback()
                raise AccountConflictError from error
            database.refresh(user)
            return user, token

    def login(self, email: str, password: str) -> tuple[User, str]:
        with self._session_factory() as database:
            user = database.scalar(select(User).where(User.normalized_email == email.strip().casefold()))
            # Always perform the expensive verification so a missing account does
            # not have an observably faster response than a wrong password.
            encoded = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
            valid = PasswordHasher.verify(password, encoded)
            if user is None or not valid:
                raise InvalidCredentialsError
            token = self._create_session(database, user.id)
            database.commit()
            return user, token

    def resolve(self, token: str | None) -> User | None:
        if not token:
            return None
        now = datetime.now(UTC).replace(tzinfo=None)
        token_hash = _token_hash(token)
        with self._session_factory() as database:
            auth_session = database.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
            if auth_session is None:
                return None
            if auth_session.expires_at <= now:
                database.delete(auth_session)
                database.commit()
                return None
            return auth_session.user

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._session_factory() as database:
            database.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
            database.commit()

    @staticmethod
    def _create_session(database: Session, user_id: int) -> str:
        settings = get_settings()
        now = datetime.now(UTC).replace(tzinfo=None)
        database.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
        stale_ids = database.scalars(
            select(AuthSession.id)
            .where(AuthSession.user_id == user_id)
            .order_by(AuthSession.created_at.desc(), AuthSession.id.desc())
            .offset(max(0, settings.auth_max_sessions_per_user - 1))
        ).all()
        if stale_ids:
            database.execute(delete(AuthSession).where(AuthSession.id.in_(stale_ids)))
        token = secrets.token_urlsafe(48)
        database.add(AuthSession(
            token_hash=_token_hash(token), user_id=user_id,
            expires_at=now + timedelta(days=settings.auth_session_days),
        ))
        return token


auth_service = AuthService(SessionLocal)


def get_optional_user(request: Request) -> User | None:
    return auth_service.resolve(request.cookies.get(get_settings().auth_cookie_name))


def get_current_user(request: Request) -> User:
    user = get_optional_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user
