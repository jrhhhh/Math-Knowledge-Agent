import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.local_fallback import local_math_answer, match_local_template
from app.database import Base
from app.models.local_template import LocalTemplate


class LocalFallbackTests(unittest.TestCase):
    def test_known_theorem_answers_are_actionable(self):
        answer = local_math_answer("柯西中值定理")
        self.assertIn("罗尔定理", answer)
        self.assertIn("ξ", answer)
        self.assertEqual(match_local_template("柯西中值定理")["id"], "cauchy_mean_value")

    def test_topology_answer_contains_mapping_proof(self):
        answer = local_math_answer("为什么连续函数把紧集映射为紧集？")
        self.assertIn("f⁻¹", answer)
        self.assertIn("有限子覆盖", answer)

    def test_unknown_question_is_honest(self):
        answer = local_math_answer("一个非常特殊的问题")
        self.assertIn("模型暂不可用", answer)

    def test_common_analysis_templates(self):
        self.assertIn("紧集", local_math_answer("连续函数在紧集上有界的原因"))
        self.assertIn("介值定理", local_math_answer("证明介值定理"))

    def test_enabled_database_template_is_used(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add(LocalTemplate(template_id="custom", pattern="自定义定理", answer="这是管理员模板。"))
        db.commit()
        self.assertEqual(match_local_template("请解释自定义定理", db)["id"], "custom")
        db.close()


if __name__ == "__main__":
    unittest.main()
