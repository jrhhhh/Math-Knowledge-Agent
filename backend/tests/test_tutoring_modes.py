import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.api.ai import AskRequest, generate_hint
from app.api.conversations import MessageCreate, ask_request, create_conversation, create_message, ConversationCreate, get_conversation
from app.database import Base
from app.models.answer_record import AnswerRecord


class TutoringModeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_hint_failure_does_not_fall_back_to_complete_solution_or_tools(self):
        with patch("app.api.ai.call_deepseek", side_effect=TimeoutError), patch("app.api.ai.local_math_answer") as full_answer:
            result = generate_hint(AskRequest(question="证明连续映射把紧集映为紧集", teaching_mode="hint", agent_mode=True), self.db, "hint-fallback")
        self.assertEqual(result["teaching_mode"], "hint")
        self.assertEqual(result["agent_tool_evidence"], [])
        self.assertIn("原像", result["answer"])
        self.assertNotIn("有限子覆盖", result["answer"])
        full_answer.assert_not_called()
        self.assertEqual(self.db.query(AnswerRecord).count(), 1)

    def test_automatic_verification_is_scoped_and_disabled_for_hints(self):
        integral = "求定积分 x²，x 从 0 到 1。"
        self.assertTrue(ask_request(MessageCreate(content=integral, automatic_verification=True), integral).agent_mode)
        self.assertFalse(ask_request(MessageCreate(content=integral, automatic_verification=True, teaching_mode="hint"), integral).agent_mode)
        self.assertFalse(ask_request(MessageCreate(content="证明连续映射保持紧性", automatic_verification=True), "context").agent_mode)
        self.assertFalse(ask_request(MessageCreate(content=integral), integral).agent_mode)

    def test_mode_and_original_question_survive_followup_and_restore(self):
        conversation = create_conversation(ConversationCreate(), self.db)
        for mode, text in (("hint", "证明连续映射把紧集映为紧集"), ("explain", "这一步的原像为什么是开集？")):
            result = {"answer": "教学内容", "answer_id": 7, "teaching_mode": mode}
            with patch("app.api.conversations._ask_impl", return_value=result) as asked:
                create_message(conversation["id"], MessageCreate(content=text, teaching_mode=mode), self.db)
                request = asked.call_args.args[0]
                self.assertEqual(request.current_question, text)
                self.assertEqual(request.teaching_mode, mode)
                self.assertIn("连续映射", request.question)
        restored = get_conversation(conversation["id"], self.db)
        self.assertEqual(restored["messages"][0]["metadata"]["teaching_mode"], "hint")
        self.assertEqual(restored["messages"][-1]["metadata"]["teaching_mode"], "explain")

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValidationError):
            MessageCreate(content="题目", teaching_mode="unknown")

    def test_truncated_formula_is_replaced_by_complete_hint(self):
        with patch("app.api.ai.call_deepseek", return_value=r"先考虑 \(f^{-1}(U_i"):
            result = generate_hint(AskRequest(question="连续映射把紧集映成紧集", teaching_mode="hint"), self.db, "truncated-hint")
        self.assertEqual(result["answer_source"], "local_hint")
        self.assertTrue(result["answer"].endswith("。"))
