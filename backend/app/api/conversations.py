"""Durable, context-aware conversations built on the existing Math Agent engine."""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.conversation import Conversation, ConversationMessage, MessageConcept
from app.models.concept import Concept
from app.api.ai import AskRequest, _ask_impl, classify_ai_error, RequestCancelledError, set_task_status


router = APIRouter(prefix="/conversations", tags=["Conversations"])


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    topic: str | None = Field(default=None, max_length=160)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    topic: str | None = Field(default=None, max_length=160)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=12000)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def serialize_message(message: ConversationMessage):
    return {
        "id": message.id, "conversation_id": message.conversation_id, "role": message.role,
        "content": message.content, "status": message.status, "answer_id": message.answer_id,
        "request_id": message.request_id, "created_at": message.created_at.isoformat(),
        "metadata": json.loads(message.metadata_json) if message.metadata_json else None,
    }


def serialize_conversation(item: Conversation, message_count: int | None = None):
    return {
        "id": item.id, "title": item.title, "topic": item.topic, "summary": item.summary,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
        "message_count": message_count,
    }


def get_conversation_or_404(conversation_id: int, db: Session):
    item = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return item


def refresh_summary(conversation: Conversation, db: Session):
    """Keep a deterministic, bounded long-term memory for old turns."""
    messages = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conversation.id).order_by(ConversationMessage.id.asc()).all()
    older = messages[:-8]
    if not older:
        return
    digest = []
    for message in older[-12:]:
        label = "用户" if message.role == "user" else "助手"
        compact = " ".join(message.content.split())[:260]
        digest.append(f"{label}：{compact}")
    conversation.summary = "\n".join(digest)[-3600:]


def build_context_prompt(conversation: Conversation, newest: str, db: Session):
    messages = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conversation.id).order_by(ConversationMessage.id.desc()).limit(8).all()
    messages.reverse()
    recent = "\n".join(
        f"{'用户' if item.role == 'user' else '助手'}：{item.content[:1800]}" for item in messages if item.content.strip()
    )
    summary = conversation.summary or "（这是对话的开始）"
    return (
        "你是 Math Agent，一名严谨、善于教学的数学助手。请延续同一段对话，"
        "把‘继续’、‘这一步’等指代与上下文准确关联。不要复述以下上下文，不要编造已证明结论。\n\n"
        f"【长期对话摘要】\n{summary}\n\n【最近对话】\n{recent}\n\n"
        f"【用户最新问题】\n{newest}\n\n"
        "请直接给出结构清晰的数学回答；证明题要说明使用的条件和每一步依据。"
    )


def persist_answer(conversation: Conversation, user_message: ConversationMessage, result: dict, db: Session):
    assistant = ConversationMessage(
        conversation_id=conversation.id, role="assistant", content=result.get("answer", ""),
        status="completed", answer_id=result.get("answer_id"), request_id=result.get("request_id"),
        metadata_json=json.dumps({key: result.get(key) for key in ("answer_source", "answer_quality", "knowledge_graph", "formula_fixes")}, ensure_ascii=False),
    )
    db.add(assistant)
    conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if conversation.title == "新的数学对话":
        conversation.title = user_message.content.strip().replace("\n", " ")[:42]
    db.flush()
    for item in result.get("concepts") or []:
        concept_id = item.get("id")
        if concept_id and db.query(Concept).filter(Concept.id == concept_id).first():
            db.add(MessageConcept(message_id=assistant.id, concept_id=concept_id, relevance=round(float(item.get("similarity", 1)) * 100)))
    refresh_summary(conversation, db)
    db.commit()
    db.refresh(assistant)
    return assistant


@router.post("", status_code=201)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    item = Conversation(title=(payload.title or "新的数学对话").strip(), topic=payload.topic)
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize_conversation(item, 0)


@router.get("")
def list_conversations(db: Session = Depends(get_db)):
    items = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    saved_items = []
    for item in items:
        message_count = db.query(ConversationMessage).filter_by(conversation_id=item.id).count()
        if message_count:
            saved_items.append(serialize_conversation(item, message_count))
    return {"items": saved_items}


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    item = get_conversation_or_404(conversation_id, db)
    messages = db.query(ConversationMessage).filter_by(conversation_id=item.id).order_by(ConversationMessage.id.asc()).all()
    return {"conversation": serialize_conversation(item, len(messages)), "messages": [serialize_message(message) for message in messages]}


@router.patch("/{conversation_id}")
def update_conversation(conversation_id: int, payload: ConversationUpdate, db: Session = Depends(get_db)):
    item = get_conversation_or_404(conversation_id, db)
    if payload.title is not None:
        item.title = payload.title.strip()
    if payload.topic is not None:
        item.topic = payload.topic
    db.commit()
    db.refresh(item)
    return serialize_conversation(item)


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    item = get_conversation_or_404(conversation_id, db)
    message_ids = [message_id for (message_id,) in db.query(ConversationMessage.id).filter_by(conversation_id=item.id).all()]
    if message_ids:
        db.query(MessageConcept).filter(MessageConcept.message_id.in_(message_ids)).delete(synchronize_session=False)
    db.query(ConversationMessage).filter_by(conversation_id=item.id).delete(synchronize_session=False)
    db.delete(item)
    db.commit()
    return {"deleted": conversation_id}


@router.post("/{conversation_id}/messages")
def create_message(conversation_id: int, payload: MessageCreate, db: Session = Depends(get_db)):
    conversation = get_conversation_or_404(conversation_id, db)
    content = payload.content.strip()
    user_message = ConversationMessage(conversation_id=conversation.id, role="user", content=content)
    db.add(user_message)
    db.commit()
    prompt = build_context_prompt(conversation, content, db)
    result = _ask_impl(AskRequest(question=prompt), db, request_id=uuid4().hex[:12])
    assistant = persist_answer(conversation, user_message, result, db)
    return {"user_message": serialize_message(user_message), "assistant_message": serialize_message(assistant), "result": result}


@router.post("/{conversation_id}/messages/stream")
async def stream_message(conversation_id: int, payload: MessageCreate):
    async def events():
        db = SessionLocal()
        task = None
        cancel_event = threading.Event()
        sequence = 0
        try:
            conversation = get_conversation_or_404(conversation_id, db)
            content = payload.content.strip()
            user_message = ConversationMessage(conversation_id=conversation.id, role="user", content=content, status="completed")
            db.add(user_message)
            db.commit()
            db.refresh(user_message)
            sequence += 1
            yield f"id: {sequence}\nevent: user\ndata: {json.dumps(serialize_message(user_message), ensure_ascii=False)}\n\n"
            prompt = build_context_prompt(conversation, content, db)
            chunks = queue.Queue()
            request_id = uuid4().hex[:12]
            task = asyncio.create_task(asyncio.to_thread(_ask_impl, AskRequest(question=prompt), db, chunks.put, request_id, cancel_event))
            while not task.done():
                while not chunks.empty():
                    sequence += 1
                    yield f"id: {sequence}\nevent: token\ndata: {json.dumps({'text': chunks.get_nowait()}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.08)
            while not chunks.empty():
                sequence += 1
                yield f"id: {sequence}\nevent: token\ndata: {json.dumps({'text': chunks.get_nowait()}, ensure_ascii=False)}\n\n"
            result = await task
            assistant = persist_answer(conversation, user_message, result, db)
            sequence += 1
            payload_data = {"assistant_message": serialize_message(assistant), "result": result}
            yield f"id: {sequence}\nevent: result\ndata: {json.dumps(payload_data, ensure_ascii=False)}\n\n"
        except Exception as exc:
            if isinstance(exc, RequestCancelledError):
                status, detail = "cancelled", "对话生成已取消"
            else:
                status, detail = "failed", classify_ai_error(exc)[1]
            cancel_event.set()
            set_task_status(None, status, detail, str(exc), db=db)
            sequence += 1
            yield f"id: {sequence}\nevent: error\ndata: {json.dumps({'detail': detail}, ensure_ascii=False)}\n\n"
        finally:
            cancel_event.set()
            if task is not None and not task.done():
                try:
                    await asyncio.shield(task)
                except BaseException:
                    pass
            db.close()
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
