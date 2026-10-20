from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.core.security import (
    DEV_USER_ID,
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.schemas.api import AuthOut, LoginIn, SignupIn, TokenOut, UserOut
from app.services.experiments.recorder import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_out(user: models.User) -> AuthOut:
    return AuthOut(access_token=create_access_token(user.id, user.email, user.role),
                   user=UserOut.model_validate(user))


@router.post("/signup", response_model=AuthOut, status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(409, "email already registered")
    # Pehla real user admin banta hai; baaki analyst (admin baad me role badal sakta hai)
    has_users = db.scalar(select(func.count()).select_from(models.User)
                          .where(models.User.id != DEV_USER_ID)) > 0
    user = models.User(email=email, name=body.name, role="analyst" if has_users else "admin",
                       password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    log_audit(db, user.id, "signup", object_ref=user.id)
    return _auth_out(user)


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        log_audit(db, None, "login_failed", object_ref=body.email[:255], blocked=True, reason="invalid credentials")
        raise HTTPException(401, "invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "account disabled")
    log_audit(db, user.id, "login", object_ref=user.id)
    return _auth_out(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(models.User, user.id)
    if row is None:  # auth_disabled dev user
        return UserOut(id=user.id, email=user.email, role=user.role)
    return row


@router.post("/dev-token", response_model=TokenOut)
def dev_token(role: str = "admin"):
    """Sirf AUTH_DISABLED=true (local testing) me."""
    if not get_settings().auth_disabled:
        raise HTTPException(404)
    return TokenOut(access_token=create_access_token(DEV_USER_ID, "dev@local", role))
