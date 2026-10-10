import unittest,tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from app.database import Base
from app.api.textbooks import extract_pages,store_pdf,get_textbook,edit_chunk,chunk_revisions,read_original,edit_document
from app.models.chunk_revision import ChunkRevision
from app.models.knowledge_source import KnowledgeDocument
class TextbookImportTests(unittest.TestCase):
    def test_pdf_pages_start_unreviewed_and_edits_keep_original(self):
        writer=PdfWriter();page=writer.add_blank_page(300,400)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 30 300 Td (A implies B) Tj ET');page[NameObject('/Contents')]=writer._add_object(content)
        writer.add_blank_page(300,400);buf=BytesIO();writer.write(buf);data=buf.getvalue();pages=extract_pages(data)
        self.assertIn('A implies B',pages[0]);self.assertEqual(pages[1],'')
        engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine);db=sessionmaker(bind=engine)()
        with tempfile.TemporaryDirectory() as root,patch('app.api.textbooks.UPLOAD_DIR',Path(root)):
            result=store_pdf(data,pages,'测试教材','测试课程','第1章',db);self.assertEqual(result['review_status'],'draft');self.assertEqual(result['empty_pages'],1)
            book=get_textbook(result['id'],db);self.assertTrue(book['has_original']);self.assertEqual(len(book['chunks']),2)
            chunk=book['chunks'][0];edit_chunk(chunk['id'],{'content':r'A\(\Rightarrow\)B','review_status':'approved'},db)
            revisions=chunk_revisions(chunk['id'],db)['items'];self.assertIn('A implies B',revisions[-1]['content']);self.assertEqual(len(revisions),2)
            with self.assertRaises(Exception):edit_chunk(book['chunks'][1]['id'],{'content':'','review_status':'approved'},db)
            edit_document(book['id'],{'review_status':'approved'},db);self.assertEqual(get_textbook(book['id'],db)['review_status'],'approved')
            response=read_original(book['id'],db);self.assertEqual(Path(response.path).read_bytes(),data)
            old=KnowledgeDocument(title='禁止路径',course='测试',source_uri='/etc/passwd');db.add(old);db.commit()
            with self.assertRaises(Exception):read_original(old.id,db)
        db.close()
    def test_invalid_pdf_is_rejected(self):
        for data in (b'not pdf',b'%PDF-broken'):
            with self.assertRaises(Exception):extract_pages(data)
