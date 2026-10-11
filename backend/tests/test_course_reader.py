import json
import threading
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.knowledge_source import KnowledgeDocument, KnowledgeChunk
from app.models.chunk_revision import ChunkRevision
from app.models.course_reading import CourseMessage, CourseExerciseDraft
from app.models.study_note import StudyNote
from app.api.course_reader import (ReadingScope, ReadingQuestion, StateUpdate, resolve_scope, new_conversation, get_state, update_state, get_conversation, generate_reply, save_note, approve_draft, DraftReview, build_messages)
from app.api.textbooks import edit_chunk
from fastapi import HTTPException

class CourseReaderTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine)()
        self.a=KnowledgeDocument(title='教材 A',course='数学分析',review_status='draft')
        self.b=KnowledgeDocument(title='教材 B',course='线性代数',review_status='draft')
        self.db.add_all([self.a,self.b]);self.db.flush()
        self.chunks=[]
        for book in [self.a,self.b]:
            for p,text in [(1,'连续函数在紧集上的像仍然紧。'),(2,'直接证明从已知条件开始，逐步得到结论。'),(3,'')]:
                chunk=KnowledgeChunk(document_id=book.id,page_start=p,page_end=p,content=text,review_status='unreviewed');self.db.add(chunk);self.chunks.append(chunk)
        self.db.commit()
        self.chat=new_conversation(self.a.id,self.db)['id']
    def tearDown(self):
        self.db.close();self.engine.dispose()
    def test_scope_limits_foreign_chunks_and_selection(self):
        base=ReadingScope(start=1,end=1)
        self.assertEqual(resolve_scope(self.a.id,base,self.db)['sources'][0]['review_status'],'unreviewed')
        for scope in [ReadingScope(start=1,end=4),ReadingScope(start=2,end=1),ReadingScope(start=1,end=2),ReadingScope(start=1,end=1,chunk_ids=[self.chunks[3].id]),ReadingScope(start=3,end=3),ReadingScope(start=1,end=1,mode='selection',selection='伪造的教材文字')]:
            with self.assertRaises(HTTPException):resolve_scope(self.a.id,scope,self.db)
        selected=resolve_scope(self.a.id,ReadingScope(start=1,end=1,mode='selection',selection='连续 函数'),self.db)
        self.assertEqual(selected['selection'],'连续 函数')
    def test_state_is_book_bound_and_validated(self):
        update_state(self.a.id,StateUpdate(page=2,zoom=1.25,bookmarks=[2,2],panel_ratio=.6,conversation_id=self.chat),self.db)
        self.assertEqual(get_state(self.a.id,self.db)['bookmarks'],[2])
        self.assertEqual(get_state(self.b.id,self.db)['page'],1)
        for payload in [StateUpdate(page=4),StateUpdate(bookmarks=[-1]),StateUpdate(conversation_id=self.chat)]:
            with self.assertRaises(HTTPException):update_state(self.b.id,payload,self.db)
        with self.assertRaises(HTTPException):get_conversation(self.b.id,self.chat,self.db)
    def generate(self,action='explain'):
        payload=ReadingQuestion(question='解释这个结论',action=action,scope=ReadingScope(start=1,end=1))
        snapshot=resolve_scope(self.a.id,payload.scope,self.db)
        tokens=[]
        value=json.dumps({'title':'连续函数','content':'证明像集紧。','solution':'拉回开覆盖。'},ensure_ascii=False) if action=='quiz' else '教材依据 [PDF p1]：连续函数在紧集上的像仍然紧。补充解释：需要连续性。'
        with patch('app.api.course_reader.call_deepseek',return_value=value):
            result=generate_reply(self.a.id,self.chat,payload,snapshot,threading.Event(),lambda k,d:tokens.append((k,d)),self.db)
        return result,snapshot
    def test_snapshot_and_note_survive_source_changes(self):
        result,snapshot=self.generate()
        before=result['assistant']['context']['source_hash']
        edit_chunk(self.chunks[0].id,{'content':'修改后的教材内容','review_status':'unreviewed'},self.db)
        history=get_conversation(self.a.id,self.chat,self.db)['items']
        self.assertEqual(history[-1]['context']['source_hash'],before)
        self.assertIn('连续函数',history[-1]['context']['sources'][0]['content'])
        note=save_note(self.a.id,result['assistant']['id'],self.db)
        origin=json.loads(self.db.get(StudyNote,note['id']).origin_json)
        self.assertEqual(origin['reading_context']['source_hash'],before)
        self.assertEqual(save_note(self.a.id,result['assistant']['id'],self.db)['id'],note['id'])
        with self.assertRaises(HTTPException):save_note(self.b.id,result['assistant']['id'],self.db)
    def test_selection_exposes_only_selected_material(self):
        payload=ReadingQuestion(question='这是什么意思',scope=ReadingScope(mode='selection',start=2,end=2,selection='从已知条件开始'))
        snapshot=resolve_scope(self.a.id,payload.scope,self.db)
        prompt=build_messages(self.chat,payload,snapshot,self.db)[-1]['content']
        self.assertIn('从已知条件开始',prompt)
        self.assertNotIn('逐步得到结论',prompt)
    def test_cancel_does_not_save_assistant(self):
        cancel=threading.Event();cancel.set()
        payload=ReadingQuestion(question='解释',scope=ReadingScope(start=1,end=1))
        snapshot=resolve_scope(self.a.id,payload.scope,self.db)
        with patch('app.api.course_reader.call_deepseek',return_value='不能入库的回答') as provider:
            with self.assertRaises(Exception):generate_reply(self.a.id,self.chat,payload,snapshot,cancel,lambda *args:None,self.db)
        provider.assert_not_called()
        self.assertEqual(self.db.query(CourseMessage).filter_by(role='assistant').count(),0)
        self.assertEqual(self.db.query(CourseMessage).first().status,'cancelled')
    def test_quiz_stays_draft_until_explicit_review_and_is_idempotent(self):
        result,snapshot=self.generate('quiz');draft=self.db.get(CourseExerciseDraft,result['draft_id'])
        self.assertEqual(draft.status,'draft');self.assertIsNone(draft.problem_id)
        with self.assertRaises(HTTPException):approve_draft(self.a.id,draft.id,DraftReview(title=draft.title,content=draft.content,solution=draft.solution),self.db)
        payload=DraftReview(title='经核对的题目',content=draft.content,solution=draft.solution,confirmed=True)
        approved=approve_draft(self.a.id,draft.id,payload,self.db)
        self.assertEqual(approve_draft(self.a.id,draft.id,payload,self.db)['problem_id'],approved['problem_id'])
        with self.assertRaises(HTTPException):approve_draft(self.b.id,draft.id,payload,self.db)

    def test_quiz_restores_escaped_newlines_without_changing_tex(self):
        payload=ReadingQuestion(question='练习',action='quiz',scope=ReadingScope(start=1,end=1))
        snapshot=resolve_scope(self.a.id,payload.scope,self.db)
        fields={'title':'真值表','content':'判断命题','solution':r'第一行\n第二行：\(\neg A\) 和 \(\nabla f\)'}
        with patch('app.api.course_reader.call_deepseek',return_value=json.dumps(fields)):
            result=generate_reply(self.a.id,self.chat,payload,snapshot,threading.Event(),lambda *args:None,self.db)
        solution=self.db.get(CourseExerciseDraft,result['draft_id']).solution
        self.assertIn('第一行\n第二行',solution)
        self.assertIn(r'\neg A',solution)
        self.assertIn(r'\nabla f',solution)

    def test_graph_book_bound_snapshot_cache_and_candidate(self):
        from app.api.course_reader import generate_reading_graph
        from app.api.ai import get_graph_candidate
        result,snapshot=self.generate()
        graph={'nodes':[{'id':'a','name':'连续函数','type':'concept'},{'id':'b','name':'紧集','type':'concept'}], 'edges':[{'source':'a','target':'b','relation':'related'}]}
        with patch('app.api.ai.call_deepseek',return_value=json.dumps(graph,ensure_ascii=False)) as model:
            generated=generate_reading_graph(self.a.id,self.chat,self.db)
            self.assertEqual(generate_reading_graph(self.a.id,self.chat,self.db)['candidate_id'],generated['candidate_id'])
            self.assertEqual(model.call_count,1)
        saved=get_graph_candidate(generated['candidate_id'],self.db)
        self.assertEqual(saved['status'],'pending')
        self.assertIsNone(saved['conversation_id'])
        self.assertEqual(saved['source_message_ids'],[])
        self.assertTrue(saved['evidence'])
        for item in saved['evidence']:
            self.assertIsNone(item['source_message_id'])
            self.assertEqual(item['context']['reading_context']['source_hash'],snapshot['source_hash'])
            self.assertEqual(item['context']['reading_context']['document_id'],self.a.id)
        edit_chunk(self.chunks[0].id,{'content':'改动原文','review_status':'unreviewed'},self.db)
        self.assertEqual(get_graph_candidate(saved['id'],self.db)['evidence'],saved['evidence'])
        with self.assertRaises(HTTPException):generate_reading_graph(self.b.id,self.chat,self.db)

    def test_graph_requires_completed_answer(self):
        from app.api.course_reader import generate_reading_graph
        with patch('app.api.ai.call_deepseek') as model:
            with self.assertRaises(HTTPException):generate_reading_graph(self.a.id,self.chat,self.db)
            self.db.add(CourseMessage(conversation_id=self.chat,role='assistant',content='失败',status='failed',context_json='{}',request_id='failed'))
            self.db.commit()
            with self.assertRaises(HTTPException):generate_reading_graph(self.a.id,self.chat,self.db)
            model.assert_not_called()
