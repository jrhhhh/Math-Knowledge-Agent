"""Local PDF import, reversible text revisions, and explicit source approval."""
import asyncio
from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pypdf import PdfReader
from sqlalchemy.orm import Session
from app.api.knowledge import get_db, document_response
from app.models.knowledge_source import KnowledgeDocument,KnowledgeChunk
from app.models.chunk_revision import ChunkRevision

router=APIRouter(prefix='/textbooks',tags=['Textbooks'])
UPLOAD_DIR=Path(__file__).resolve().parents[2]/'uploads'/'textbooks'
MAX_BYTES=50*1024*1024
STATUSES={'draft','unreviewed','approved','rejected'}

def extract_pages(data):
    if not data.startswith(b'%PDF-'):raise HTTPException(422,detail='请选择有效 PDF 文件')
    try:
        reader=PdfReader(BytesIO(data))
        if reader.is_encrypted:raise HTTPException(422,detail='暂不支持加密 PDF，请先提供可读取副本')
        if not 1<=len(reader.pages)<=1000:raise HTTPException(422,detail='PDF 应为 1 至 1000 页')
        pages=[];total=0
        for page in reader.pages:
            stream=page.get_contents()
            if stream is not None and len(stream.get_data())>10*1024*1024:raise HTTPException(422,detail='单页内容过大，请拆分后导入')
            content=(page.extract_text() or '').strip()
            total+=len(content)
            if len(content)>100000 or total>3000000:raise HTTPException(422,detail='提取文本过长，请分章导入')
            pages.append(content)
        return pages
    except HTTPException:raise
    except Exception:raise HTTPException(422,detail='PDF 无法解析，请检查文件是否损坏')

def store_pdf(data,pages,title,course,chapter,db):
    name=uuid4().hex+'.pdf';UPLOAD_DIR.mkdir(parents=True,exist_ok=True);path=UPLOAD_DIR/name
    document=KnowledgeDocument(title=title.strip(),course=course.strip(),chapter=chapter.strip(),source_uri='upload://'+name,review_status='draft')
    try:
        path.write_bytes(data);db.add(document);db.flush()
        for number,content in enumerate(pages,1):
            chunk=KnowledgeChunk(document_id=document.id,page_start=number,page_end=number,heading=chapter.strip() or f'第 {number} 页',content=content,chunk_type='explanation',review_status='unreviewed');db.add(chunk);db.flush()
            db.add(ChunkRevision(chunk_id=chunk.id,content=content,heading=chunk.heading,review_status='unreviewed',reason='PDF 首次提取；需与原页核对'))
        db.commit();db.refresh(document)
    except Exception:
        db.rollback();path.unlink(missing_ok=True);raise
    return {**document_response(document,len(pages)),'empty_pages':sum(not x for x in pages),'message':'导入完成，尚未审核；请对照原页校对公式与文本。'}

@router.post('/upload')
async def upload_pdf(request:Request,title:str=Query(min_length=1,max_length=240),course:str=Query(min_length=1,max_length=160),chapter:str=Query(default='',max_length=160),db:Session=Depends(get_db)):
    if not title.strip() or not course.strip():raise HTTPException(422,detail='标题和课程不能为空')
    data=bytearray()
    async for part in request.stream():
        if len(data)+len(part)>MAX_BYTES:raise HTTPException(413,detail='PDF 不可超过 50 MB，请分章导入')
        data.extend(part)
    pages=await asyncio.to_thread(extract_pages,bytes(data))
    return store_pdf(bytes(data),pages,title,course,chapter,db)

def original_path(document):
    match=re.fullmatch(r'upload://([a-f0-9]{32}\.pdf)',document.source_uri or '')
    return UPLOAD_DIR/match.group(1) if match else None

@router.get('/{document_id}')
def get_textbook(document_id:int,db:Session=Depends(get_db)):
    document=db.query(KnowledgeDocument).filter_by(id=document_id).first()
    if not document:raise HTTPException(404,detail='教材不存在')
    chunks=db.query(KnowledgeChunk).filter_by(document_id=document_id).order_by(KnowledgeChunk.page_start,KnowledgeChunk.id).all();path=original_path(document)
    return {**document_response(document,len(chunks)),'has_original':bool(path and path.is_file()),'chunks':[{'id':x.id,'page_start':x.page_start,'heading':x.heading,'content':x.content,'review_status':x.review_status} for x in chunks]}

@router.get('/{document_id}/file')
def read_original(document_id:int,db:Session=Depends(get_db)):
    document=db.query(KnowledgeDocument).filter_by(id=document_id).first()
    if not document:raise HTTPException(404,detail='教材不存在')
    path=original_path(document)
    if not path or not path.is_file():raise HTTPException(404,detail='暂无已上传的原文件，请通过导入 PDF 附加原稿')
    return FileResponse(path,media_type='application/pdf',headers={'Content-Disposition':'inline; filename="textbook.pdf"'})

@router.put('/{document_id}')
def edit_document(document_id:int,payload:dict,db:Session=Depends(get_db)):
    document=db.query(KnowledgeDocument).filter_by(id=document_id).first()
    if not document:raise HTTPException(404,detail='教材不存在')
    values={}
    for key,limit in [('title',240),('course',160),('chapter',160)]:
        if key in payload:
            value=str(payload[key] or '').strip()
            if len(value)>limit or (key!='chapter' and not value):raise HTTPException(422,detail=f'{key} 内容无效')
            values[key]=value
    status=payload.get('review_status',document.review_status)
    if status not in STATUSES:raise HTTPException(422,detail='审核状态无效')
    for key,value in values.items():setattr(document,key,value)
    document.review_status=status;db.commit();return document_response(document)

@router.put('/chunks/{chunk_id}')
def edit_chunk(chunk_id:int,payload:dict,db:Session=Depends(get_db)):
    chunk=db.query(KnowledgeChunk).filter_by(id=chunk_id).first()
    if not chunk:raise HTTPException(404,detail='片段不存在')
    content=str(payload.get('content',chunk.content));heading=str(payload.get('heading',chunk.heading) or '')
    status=payload.get('review_status','unreviewed')
    if status not in STATUSES or len(content)>100000 or len(heading)>240:raise HTTPException(422,detail='片段内容或审核状态无效')
    if status=='approved' and not content.strip():raise HTTPException(422,detail='空文本不能标为已审核，请对照原页补录')
    if not db.query(ChunkRevision).filter_by(chunk_id=chunk_id).first():db.add(ChunkRevision(chunk_id=chunk_id,content=chunk.content,heading=chunk.heading,review_status=chunk.review_status,reason='编辑前原文'))
    chunk.content=content;chunk.heading=heading;chunk.review_status=status
    db.add(ChunkRevision(chunk_id=chunk.id,content=content,heading=heading,review_status=status,reason=str(payload.get('reason') or '用户校对')[:240]));db.commit()
    return {'id':chunk.id,'content':chunk.content,'heading':chunk.heading,'review_status':chunk.review_status}

@router.get('/chunks/{chunk_id}/revisions')
def chunk_revisions(chunk_id:int,db:Session=Depends(get_db)):
    return {'items':[{'id':x.id,'content':x.content,'heading':x.heading,'review_status':x.review_status,'reason':x.reason,'created_at':x.created_at.isoformat()} for x in db.query(ChunkRevision).filter_by(chunk_id=chunk_id).order_by(ChunkRevision.id.desc()).all()]}
