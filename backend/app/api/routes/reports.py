from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.api import ReportIn

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.Report, models.SavedQuery)
        .join(models.SavedQuery, models.Report.saved_query_id == models.SavedQuery.id)
        .where(models.Report.user_id == user.id)
    ).all()
    return [{"id": r.id, "name": r.name, "schedule": r.schedule, "question": q.question, "sql": q.sql}
            for r, q in rows]


@router.post("")
def create_report(body: ReportIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    sq = models.SavedQuery(user_id=user.id, name=body.name, question=body.question, sql=body.sql,
                           chart_spec=body.chart_spec)
    db.add(sq)
    db.flush()
    report = models.Report(user_id=user.id, name=body.name, saved_query_id=sq.id, schedule=body.schedule)
    db.add(report)
    db.commit()
    # TODO(phase-8): schedule != None ho to Celery beat job register karo
    return {"id": report.id, "saved_query_id": sq.id}
