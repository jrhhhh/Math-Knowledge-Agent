"""Local-personal product metrics with auditable cohorts and no inferred retention."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from statistics import median
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from app.api.learning import get_db
from app.models.problem_attempt import ProblemAttempt
from app.models.problem import Problem
from app.models.answer_record import AnswerRecord, AnswerFeedback
from app.models.learning_visit import LearningVisit

router=APIRouter(prefix='/learning',tags=['Learning Metrics'])

@router.post('/visit')
def record_visit(db:Session=Depends(get_db)):
    now=datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    db.execute(insert(LearningVisit).values(local_day=day,created_at=now.replace(tzinfo=None)).on_conflict_do_nothing(index_elements=['local_day']))
    db.commit()
    row=db.query(LearningVisit).filter_by(local_day=day).one()
    return {'id':row.id,'local_day':row.local_day}


def metric_snapshot(db,days=30,now=None):
    now=now or datetime.utcnow()
    cutoff=now-timedelta(days=days) if days else datetime.min
    attempts=db.query(ProblemAttempt).filter(ProblemAttempt.created_at>=cutoff,ProblemAttempt.created_at<=now).order_by(ProblemAttempt.created_at,ProblemAttempt.id).all()
    grouped={}
    for a in attempts:grouped.setdefault(a.problem_id,[]).append(a)
    titles={x.id:x.title for x in db.query(Problem).filter(Problem.id.in_(grouped)).all()} if grouped else {}
    reviewed_count=repeat_count=delayed_count=0
    evidence=[];waits=[];invalid_waits=0;pending=0
    for problem_id,items in grouped.items():
        reviewed=[a for a in items if a.status=='reviewed' and a.correctness!='unverified' and a.reviewed_at and a.created_at<=a.reviewed_at<=now]
        reviewed_count+=bool(reviewed)
        repeat_pairs=[];delayed_pairs=[]
        for a in items:
            if a.correctness=='unverified':pending+=1
            if a.reviewed_at and a.correctness!='unverified':
                wait=(a.reviewed_at-a.created_at).total_seconds()
                if a.created_at<=a.reviewed_at<=now:waits.append(wait)
                else:invalid_waits+=1
            prior=[r for r in reviewed if (r.created_at,r.id)<(a.created_at,a.id) and r.reviewed_at<a.created_at]
            if prior:
                # Most recent earlier feedback is the anchor; each submission is counted once.
                anchor=max(prior,key=lambda x:(x.reviewed_at,x.id))
                pair={'feedback_attempt_id':anchor.id,'attempt_id':a.id,'delay_seconds':(a.created_at-anchor.reviewed_at).total_seconds()}
                repeat_pairs.append(pair)
                if pair['delay_seconds']>=86400 and a in reviewed and a.correctness=='correct' and a.independent=='yes' and a.hint_level==0 and not a.parent_attempt_id:delayed_pairs.append(pair)
        repeat_count+=bool(repeat_pairs);delayed_count+=bool(delayed_pairs)
        evidence.append({'problem_id':problem_id,'title':titles.get(problem_id,''),'attempt_ids':[a.id for a in items],
            'reviewed_attempt_ids':[a.id for a in reviewed],'repeat_pairs':repeat_pairs,'delayed_success_pairs':delayed_pairs,
            'attempts':[{'id':a.id,'created_at':a.created_at.isoformat(),'reviewed_at':a.reviewed_at.isoformat() if a.reviewed_at else None,'correctness':a.correctness,'independent':a.independent,'hint_level':a.hint_level,'parent_attempt_id':a.parent_attempt_id} for a in items]})
    answers=db.query(AnswerRecord).filter(AnswerRecord.created_at>=cutoff,AnswerRecord.created_at<=now).all()
    ids=[a.id for a in answers];latest={}
    feedback=db.query(AnswerFeedback).filter(AnswerFeedback.answer_id.in_(ids),AnswerFeedback.created_at<=now).order_by(AnswerFeedback.created_at,AnswerFeedback.id).all() if ids else []
    for f in feedback:latest[f.answer_id]=f
    visits=db.query(LearningVisit).filter(LearningVisit.created_at>=cutoff,LearningVisit.created_at<=now).order_by(LearningVisit.created_at).all()
    first=db.query(LearningVisit).order_by(LearningVisit.created_at).first()
    durations=[a.duration_seconds for a in answers if a.duration_seconds is not None and a.duration_seconds>=0]
    return {'as_of':now.isoformat()+'Z','days':days,'cutoff':cutoff.isoformat()+'Z' if days else None,
        'funnel':{'submitted_problems':len(grouped),'reviewed_problems':reviewed_count,'repeated_after_feedback':repeat_count,'delayed_independent_success':delayed_count},
        'feedback':{'submitted_attempts':len(attempts),'pending_attempts':pending,'reviewed_wait_samples':len(waits),'median_review_wait_seconds':median(waits) if waits else None,'invalid_timestamp_samples':invalid_waits,
            'answers':len(answers),'rated_answers':len(latest),'helpful_answers':sum(f.rating>=4 for f in latest.values()),'median_answer_duration_seconds':median(durations) if durations else None,'answer_duration_samples':len(durations)},
        'visits':{'active_days':len(visits),'recorded_return_days':sum(v.id!=first.id for v in visits) if first else 0,'days':[v.local_day for v in visits],'collection_started_at':first.created_at.isoformat()+'Z' if first else None,'historical_retention_available':False},
        'evidence':evidence,'answer_ids':ids,'feedback_ids':[f.id for f in latest.values()]}

@router.get('/metrics')
def metrics(days:int=30,db:Session=Depends(get_db)):
    if days not in {0,7,30}:raise HTTPException(422,"统计范围仅支持 7、30 天或全部记录")
    return metric_snapshot(db,days)
