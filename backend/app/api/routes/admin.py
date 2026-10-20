from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import DEV_USER_ID, CurrentUser, require_role
from app.db.session import get_db
from app.schemas.api import AuditOut, UserOut, UserUpdate
from app.services.experiments.recorder import log_audit

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


@router.get("/audit", response_model=list[AuditOut])
def audit(limit: int = 100, blocked_only: bool = False, db: Session = Depends(get_db)):
    q = select(models.AuditLog).order_by(models.AuditLog.ts.desc()).limit(min(limit, 500))
    if blocked_only:
        q = q.where(models.AuditLog.blocked.is_(True))
    return db.scalars(q).all()


@router.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db)):
    return db.scalars(select(models.User).where(models.User.id != DEV_USER_ID)
                      .order_by(models.User.created_at)).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, admin: CurrentUser = Depends(require_role("admin")),
                db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(409, "apna khud ka role / status nahi badal sakte")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(user, k, v)
    db.commit()
    log_audit(db, admin.id, "user_update", object_ref=user_id, reason=str(changes))
    return user
