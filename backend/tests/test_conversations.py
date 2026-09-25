import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.conversations import (
    ConversationCreate,
    ConversationUpdate,
    MessageCreate,
    create_conversation,
    create_message,
    delete_conversation,
    get_conversation,
    list_conversations,
    update_conversation,
)
from app.database import Base
from app.models.concept import Concept
from app.models.conversation import ConversationMessage


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_conversation_persists_messages_summary_and_concepts(self):
        concept = Concept(name="紧致性", type="concept", field="拓扑学")
        self.db.add(concept)
        self.db.commit()
        conversation = create_conversation(ConversationCreate(), self.db)
        result = {
            "answer": "连续映射下紧集的像仍然紧。",
            "answer_id": 5,
            "request_id": "abc123",
            "answer_source": "mock",
            "concepts": [{"id": concept.id, "similarity": 0.9}],
            "knowledge_graph": {"nodes": [], "edges": []},
        }
        with patch("app.api.conversations._ask_impl", return_value=result) as asked:
            created = create_message(conversation["id"], MessageCreate(content="为什么连续映射保持紧致性？"), self.db)
        self.assertEqual(created["assistant_message"]["content"], result["answer"])
        self.assertEqual(asked.call_count, 1)
        prompt = asked.call_args.args[0].question
        self.assertIn("为什么连续映射保持紧致性？", prompt)
        restored = get_conversation(conversation["id"], self.db)
        self.assertEqual([message["role"] for message in restored["messages"]], ["user", "assistant"])
        self.assertEqual(restored["conversation"]["title"], "为什么连续映射保持紧致性？")
        self.assertEqual(self.db.execute(__import__("sqlalchemy").text("SELECT count(*) FROM message_concepts")).scalar(), 1)
        self.assertEqual(delete_conversation(conversation["id"], self.db)["deleted"], conversation["id"])
        self.assertEqual(self.db.execute(__import__("sqlalchemy").text("SELECT count(*) FROM message_concepts")).scalar(), 0)

    def test_list_update_and_delete_conversations(self):
        first = create_conversation(ConversationCreate(title="拓扑学"), self.db)
        second = create_conversation(ConversationCreate(title="分析学"), self.db)
        self.db.add_all([
            ConversationMessage(conversation_id=first["id"], role="user", content="紧致性"),
            ConversationMessage(conversation_id=second["id"], role="user", content="分析学"),
        ])
        self.db.commit()
        update_conversation(first["id"], ConversationUpdate(title="紧致性专题", topic="拓扑学"), self.db)
        listed = list_conversations(self.db)["items"]
        self.assertEqual({item["title"] for item in listed}, {"紧致性专题", "分析学"})
        self.assertEqual(get_conversation(first["id"], self.db)["conversation"]["topic"], "拓扑学")
        self.assertEqual(delete_conversation(second["id"], self.db)["deleted"], second["id"])
        self.assertEqual(len(list_conversations(self.db)["items"]), 1)


if __name__ == "__main__":
    unittest.main()
