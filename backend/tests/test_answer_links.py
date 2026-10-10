import unittest
from app.ai.answer_links import build_answer_links


class AnswerLinkTests(unittest.TestCase):
    def test_available_source_is_not_attached_without_explicit_citation(self):
        steps = build_answer_links('因此结论成立。', [{"chunk_id": 2}], [], 'deepseek')
        self.assertEqual(steps[0]['source_chunk_ids'], [])
        self.assertEqual(steps[0]['status'], 'unverified')

    def test_explicit_citation_is_resolved_but_not_marked_correct(self):
        steps = build_answer_links('使用教材的定义 [S2]。\n\n接下来另作推导 [S99]。', [{"chunk_id": 2}], [], 'deepseek')
        self.assertEqual(steps[0]['source_chunk_ids'], [2])
        self.assertEqual(steps[0]['status'], 'source_cited')
        self.assertEqual(steps[1]['unresolved_citations'], ['S99'])
        self.assertEqual(steps[1]['source_chunk_ids'], [])

    def test_model_answer_does_not_inherit_verification_from_available_tool(self):
        tool = {"status": "computed", "value": '1/3'}
        steps = build_answer_links('结论：所有函数均连续。', [], [tool], 'deepseek')
        self.assertEqual(steps[0]['tool_ids'], [])
        self.assertEqual(steps[0]['status'], 'unverified')

    def test_deterministic_answer_separates_result_and_tool_scope(self):
        steps = build_answer_links('结论：积分为 1/3。\n原函数：x^3/3。\n适用范围：多项式。', [], [{"status": "computed"}], 'exact_calculus_tool')
        self.assertEqual(steps[0]['status'], 'scoped_calculation')
        self.assertEqual(steps[-1]['status'], 'tool_scope')
        self.assertEqual(steps[0]['tool_ids'], [1])

    def test_hint_has_no_correctness_label(self):
        steps = build_answer_links('先试着使用定义。', [], [], 'tutor_hint')
        self.assertEqual(steps[0]['status'], 'teaching_hint')
