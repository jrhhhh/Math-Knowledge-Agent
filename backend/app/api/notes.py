import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.study_note import StudyNote
from app.models.answer_record import AnswerRecord
from app.models.answer_evidence import AnswerEvidence
from app.models.conversation import ConversationMessage
router=APIRouter(prefix='/notes',tags=['Study Notes'])

def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()

def serialize(item):
    return {key:getattr(item,key) for key in ('id','title','course','content','answer_id','favorite','archived')} | {'origin':json.loads(item.origin_json),'created_at':item.created_at.isoformat(),'updated_at':item.updated_at.isoformat()}

def required_text(value, name, limit):
    text=str(value or '').strip()
    if not text or len(text)>limit: raise HTTPException(422,detail=f'{name} 应为 1 至 {limit} 字符')
    return text

@router.post('')
def create_note(payload:dict, db:Session=Depends(get_db)):
    answer_id=payload.get('answer_id');origin={};content=payload.get('content')
    if answer_id:
        answer=db.query(AnswerRecord).filter(AnswerRecord.id==answer_id).first()
        if not answer: raise HTTPException(404,detail='原回答不存在')
        evidence=db.query(AnswerEvidence).filter(AnswerEvidence.answer_id==answer.id).all()
        origin={'answer_id':answer.id,'question':answer.question,'answer':answer.answer,'answer_source':answer.answer_source,'created_at':answer.created_at.isoformat(),'evidence':[{'type':x.evidence_type,'status':x.status,'subject':x.subject,'method':x.method,'assumptions':x.assumptions,'details':json.loads(x.details) if x.details else None} for x in evidence]}
        assistant=db.query(ConversationMessage).filter(ConversationMessage.answer_id==answer.id,ConversationMessage.role=='assistant').order_by(ConversationMessage.id.desc()).first()
        if assistant:
            user=db.query(ConversationMessage).filter(ConversationMessage.conversation_id==assistant.conversation_id,ConversationMessage.role=='user',ConversationMessage.id<assistant.id).order_by(ConversationMessage.id.desc()).first()
            if user:origin['question']=user.content
        content=answer.answer
    note=StudyNote(title=required_text(payload.get('title') or origin.get('question','新笔记')[:80],'标题',240),course=required_text(payload.get('course','未分课程'),'课程',160),content=required_text(content,'笔记',100000),answer_id=answer_id,origin_json=json.dumps(origin,ensure_ascii=False))
    db.add(note);db.commit();db.refresh(note);return serialize(note)

@router.get('')
def list_notes(course:str|None=None,db:Session=Depends(get_db)):
    query=db.query(StudyNote)
    if course:query=query.filter(StudyNote.course==course)
    return {'items':[serialize(x) for x in query.order_by(StudyNote.updated_at.desc(),StudyNote.id.desc()).all()]}

@router.put('/{note_id}')
def update_note(note_id:int,payload:dict,db:Session=Depends(get_db)):
    note=db.query(StudyNote).filter(StudyNote.id==note_id).first()
    if not note:raise HTTPException(404,detail='笔记不存在')
    updates={key:required_text(payload[key],key,100000 if key=='content' else 240 if key=='title' else 160) for key in ('title','course','content') if key in payload}
    for key in ('favorite','archived'):
        if key in payload:
            if type(payload[key]) is not bool:raise HTTPException(422,detail=f'{key} 必须为布尔值')
            updates[key]=payload[key]
    for key,value in updates.items():setattr(note,key,value)
    note.updated_at=datetime.utcnow();db.commit();db.refresh(note);return serialize(note)

@router.get('/{note_id}/export')
def export_note(note_id:int,db:Session=Depends(get_db)):
    note=db.query(StudyNote).filter(StudyNote.id==note_id).first()
    if not note:raise HTTPException(404,detail='笔记不存在')
    origin=json.loads(note.origin_json)
    text=f'# {note.title}\n\n课程：{note.course}\n\n{note.content}\n\n---\n\n## 来源与验证范围\n\n笔记可经个人编辑，以下保留原始回答与证据；引用或模型审查不等于完整证明。\n\n'
    if origin:text+=f'{"伴读回答 #"+str(origin["course_message_id"]) if origin.get("course_message_id") else "原回答 #"+str(note.answer_id)}；问题：{origin["question"]}\n\n原回答：\n\n{origin["answer"]}\n\n证据快照：\n\n```json\n{json.dumps(origin["evidence"],ensure_ascii=False,indent=2)}\n```\n'
    else:text+='个人手工笔记，暂无原回答证据。\n'
    return Response(text,media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="math-note-{note_id}.md"'})
