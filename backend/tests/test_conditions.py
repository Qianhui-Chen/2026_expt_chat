import unittest

from app.conditions import format_completion_code, get_system_prompt, get_temperature


class ConditionTests(unittest.TestCase):
    def test_format_completion_code(self):
        self.assertEqual(format_completion_code("A", 1), "A001")
        self.assertEqual(format_completion_code("B", 2), "B002")

    def test_early_prompt_has_emotion_and_guidance_no_stance(self):
        anger = get_system_prompt("anger", ai_round=3)
        neutral = get_system_prompt("neutral", ai_round=2)
        self.assertIn("听了我也挺生气的", anger)
        self.assertIn("鼓励和引导用户深入反思", anger)
        self.assertIn("专业、克制的方式", neutral)
        self.assertIn("鼓励和引导用户深入反思", neutral)
        self.assertNotIn("立场设定", anger)
        self.assertNotIn("立场设定", neutral)
        self.assertNotIn("对方也有道理", anger)
        self.assertNotIn("对方也有道理", neutral)

    def test_final_prompt_has_emotion_no_stance(self):
        anger = get_system_prompt("anger", ai_round=6)
        neutral = get_system_prompt("neutral", ai_round=6)
        self.assertIn("我建议你可以试试：", anger)
        self.assertIn("根据我们的对话，我建议你可以试试：", neutral)
        self.assertNotIn("再次明确、坚定地站在用户一侧", anger)
        self.assertNotIn("再次明确、坚定地站在用户一侧", neutral)

    def test_final_round_requires_literal_advice_items(self):
        final = get_system_prompt("neutral", ai_round=6)
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
