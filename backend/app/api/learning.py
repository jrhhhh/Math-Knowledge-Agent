"""Current mastery is derived from reviewed attempts, independently of completion history."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.problem import Problem
from app.models.problem_attempt import ProblemAttempt

router = APIRouter(prefix='/learning', tags=['Learning Review'])
INTERVALS = (1, 3, 7, 14, 30)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def review_state(attempts, now=None):
    now = now or datetime.utcnow()
    reviewed = [item for item in sorted(attempts, key=lambda x:(x.created_at,x.id)) if item.correctness != 'unverified']
    if not reviewed:
        return None
    streak = 0
    first_success = None
    last_independent = None
    state = 'learning'
    for item in reviewed:
        independent = item.correctness == 'correct' and item.independent == 'yes' and item.hint_level == 0 and not item.parent_attempt_id
        if independent:
            if last_independent is None or item.created_at - last_independent >= timedelta(days=1):
                streak += 1
                first_success = first_success or item.created_at
                last_independent = item.created_at
            state = 'stable' if streak >= 3 and item.created_at - first_success >= timedelta(days=7) else 'independent_complete'
        else:
            streak = 0
            first_success = last_independent = None
            state = 'hinted_complete' if item.correctness == 'correct' else 'needs_review'
    last = reviewed[-1]
    days = INTERVALS[min(max(streak - 1,0), len(INTERVALS)-1)] if state in {'independent_complete','stable'} else 1
    anchor = last_independent if state in {'independent_complete','stable'} else last.created_at
    due = anchor + timedelta(days=days) if state != 'needs_review' else last.created_at
    pending = any(item.correctness == 'unverified' and (item.created_at,item.id) > (last.created_at,last.id) for item in attempts)
    return {'state':state,'due_at':due.isoformat(),'due':due <= now,'independent_streak':streak,
            'last_attempt_id':last.id,'last_feedback':last.feedback,'first_error_step':last.first_error_step,
            'has_error_history':any(x.correctness in {'incorrect','partially_correct'} for x in reviewed),
            'pending_retest':pending,'interval_days':days,'reviewed_count':len(reviewed)}


@router.get('/reviews')
def list_reviews(db: Session = Depends(get_db)):
    grouped = {}
    for attempt in db.query(ProblemAttempt).order_by(ProblemAttempt.created_at,ProblemAttempt.id).all():
        grouped.setdefault(attempt.problem_id,[]).append(attempt)
    now = datetime.utcnow()
    items = []
    for problem in db.query(Problem).order_by(Problem.id).all():
        state = review_state(grouped.get(problem.id,[]), now)
        if state:
            items.append({'problem_id':problem.id,'title':problem.title,'content':problem.content,**state})
    items.sort(key=lambda x:(not x['due'],x['due_at'],x['problem_id']))
    return {'items':items,'as_of':now.isoformat(),'counts':{'due':sum(x['due'] for x in items),
            'stable':sum(x['state']=='stable' for x in items),'wrong_archive':sum(x['has_error_history'] for x in items),
            'pending':sum(x['pending_retest'] for x in items)}}
