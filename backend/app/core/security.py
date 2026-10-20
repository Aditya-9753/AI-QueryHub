"""Password hashing (PBKDF2, stdlib) + JWT + RBAC. Roles: admin | analyst | viewer."""
import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.db.session import get_db

ROLES = ("admin", "analyst", "viewer")
DEV_USER_ID = "dev"
PBKDF2_ITERATIONS = 600_000

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: str
    role: str = "analyst"


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
    return hmac.compare_digest(dk, base64.b64decode(hash_b64))


# ------------------------------------------------------------------ JWT
def create_access_token(user_id: str, email: str, role: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    minutes = expires_minutes or settings.jwt_expire_minutes
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> CurrentUser:
    settings = get_settings()
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from e
    return CurrentUser(id=data["sub"], email=data.get("email", ""), role=data.get("role", "viewer"))


# ------------------------------------------------------------------ Supabase Auth
_jwks_cache: dict[str, tuple[float, dict]] = {}


def _supabase_jwks(url: str) -> dict:
    import time

    import httpx

    hit = _jwks_cache.get(url)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    jwks = httpx.get(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json", timeout=5).json()
    _jwks_cache[url] = (time.time(), jwks)
    return jwks


def is_supabase_token(token: str) -> bool:
    try:
        return str(jwt.get_unverified_claims(token).get("iss", "")).endswith("/auth/v1")
    except JWTError:
        return False


def verify_supabase_token(token: str) -> dict:
    """Supabase access token verify: legacy HS256 (SUPABASE_JWT_SECRET) ya asymmetric (project JWKS)."""
    s = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
        if alg == "HS256":
            if not s.supabase_jwt_secret:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "SUPABASE_JWT_SECRET set nahi")
            return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
        if not s.supabase_url:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "SUPABASE_URL set nahi")
        kid = jwt.get_unverified_header(token).get("kid")
        key = next((k for k in _supabase_jwks(s.supabase_url).get("keys", []) if k.get("kid") == kid), None)
        if key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown Supabase signing key")
        return jwt.decode(token, key, algorithms=[alg], audience="authenticated")
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid Supabase token") from e


def user_from_supabase(db: Session, claims: dict) -> models.User:
    """Supabase user ko local users table se map (email se); pehla user admin, baaki analyst."""
    from sqlalchemy import func, select

    email = str(claims.get("email", "")).lower()
    if not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token me email nahi")
    user = db.scalar(select(models.User).where(models.User.email == email))
    if user is None:
        others = db.scalar(select(func.count()).select_from(models.User).where(models.User.id != DEV_USER_ID))
        meta = claims.get("user_metadata") or {}
        user = models.User(email=email, name=meta.get("full_name") or meta.get("name"),
                           role="analyst" if others else "admin")
        db.add(user)
        db.commit()
    return user


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     db: Session = Depends(get_db)) -> CurrentUser:
    settings = get_settings()
    if creds is None:
        if settings.auth_disabled:
            return CurrentUser(id=DEV_USER_ID, email="dev@local", role="admin")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "login required")
    if is_supabase_token(creds.credentials):
        user = user_from_supabase(db, verify_supabase_token(creds.credentials))
        if not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user inactive")
        return CurrentUser(id=user.id, email=user.email, role=user.role)
    claims = decode_token(creds.credentials)
    if claims.id == DEV_USER_ID and settings.auth_disabled:
        return claims
    # Role DB se padho — admin ne role badla ho to turant lagu ho
    user = db.get(models.User, claims.id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return CurrentUser(id=user.id, email=user.email, role=user.role)


def require_role(*roles: str):
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"role '{user.role}' not allowed")
        return user

    return dependency
