import unittest,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.api.notes import create_note,update_note,list_notes,export_note
from app.models.answer_record import AnswerRecord
from app.models.answer_evidence import AnswerEvidence
from app.models.study_note import StudyNote
from app.models.conversation import Conversation, ConversationMessage
class StudyNoteTests(unittest.TestCase):
    def test_conversation_note_uses_actual_user_question(self):
        engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine);db=sessionmaker(bind=engine)()
        answer=AnswerRecord(request_id='test',question='internal context envelope',answer='1/3',answer_source='model');conversation=Conversation(title='积分');db.add_all([answer,conversation]);db.commit()
        db.add(ConversationMessage(conversation_id=conversation.id,role='user',content='求积分 x²'));db.flush()
        db.add(ConversationMessage(conversation_id=conversation.id,role='assistant',content='1/3',answer_id=answer.id));db.commit()
        note=create_note({'answer_id':answer.id},db)
        self.assertEqual(note['title'],'求积分 x²');self.assertEqual(note['origin']['question'],'求积分 x²');db.close()
    def test_saved_origin_remains_immutable_across_edit_archive_export(self):
        engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine);db=sessionmaker(bind=engine)()
        answer=AnswerRecord(request_id='test',question='求积分',answer='1/3',answer_source='exact_calculus_tool');db.add(answer);db.commit()
        db.add(AnswerEvidence(answer_id=answer.id,evidence_type='integral',status='computed',subject='x²',method='exact',assumptions='多项式范围',details=json.dumps({'value':'1/3'})));db.commit()
        note=create_note({'answer_id':answer.id,'course':'微积分'},db)
        changed=update_note(note['id'],{'content':'我的理解','favorite':True,'archived':True,'origin_json':'{}','answer_id':999},db)
        self.assertEqual(changed['origin']['answer'],'1/3');self.assertEqual(changed['answer_id'],answer.id)
        self.assertTrue(changed['archived']);self.assertTrue(changed['favorite']);self.assertEqual(list_notes('微积分',db)['items'][0]['content'],'我的理解')
        export=export_note(note['id'],db).body.decode();self.assertIn('多项式范围',export);self.assertIn('1/3',export);self.assertIn('我的理解',export)
        with self.assertRaises(Exception):update_note(note['id'],{'content':''},db)
        self.assertEqual(db.query(StudyNote).one().content,'我的理解');db.close()
