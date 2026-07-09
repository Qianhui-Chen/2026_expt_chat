import unittest

from app.conditions import format_completion_code, get_system_prompt, get_temperature


class ConditionTests(unittest.TestCase):
    def test_format_completion_code(self):
        self.assertEqual(format_completion_code("A", 1), "A001")
        self.assertEqual(format_completion_code("B", 2), "B002")

    def test_aligned_stance_differs_early_vs_final(self):
        early = get_system_prompt("neutral", "aligned", ai_round=3)
        final = get_system_prompt("neutral", "aligned", ai_round=6)
        self.assertIn("再次明确、坚定地站在用户一侧", final)
        self.assertNotIn("再次明确、坚定地站在用户一侧", early)
        self.assertIn("禁止引导用户从另一方的角度", early)

    def test_ambiguous_stance_differs_early_vs_final(self):
        early = get_system_prompt("neutral", "ambiguous", ai_round=2)
        final = get_system_prompt("neutral", "ambiguous", ai_round=6)
        self.assertIn("再次保持中立、不站队的立场", final)
        self.assertNotIn("再次保持中立、不站队的立场", early)
        self.assertIn("换位思考来看", early)

    def test_final_round_requires_literal_advice_items(self):
        final = get_system_prompt("neutral", "aligned", ai_round=6)
        self.assertIn("【固定建议标题】", final)
        self.assertIn("一字不改、不得同义替换、不得合并", final)
        self.assertIn("具体做法：", final)
        self.assertIn("(a) 改变伴侣对矛盾的认知；", final)

    def test_final_round_uses_lower_temperature(self):
        self.assertEqual(get_temperature("anger", ai_round=5), 0.4)
        self.assertEqual(get_temperature("anger", ai_round=6), 0.2)
        self.assertEqual(get_temperature("neutral", ai_round=6), 0.2)


if __name__ == "__main__":
    unittest.main()
