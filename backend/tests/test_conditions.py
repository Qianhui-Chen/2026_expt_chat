import unittest

from app.conditions import (
    MAX_AI_ROUNDS,
    format_completion_code,
    get_system_prompt,
    get_temperature,
    group_prompt_for,
    is_ingroup,
    is_outgroup,
    is_contingent_advice,
    is_generic_advice,
    position_from_iv,
    emotion_from_iv,
    memory_cue_from_profile,
)


class ConditionTests(unittest.TestCase):
    def test_format_completion_code(self):
        self.assertEqual(format_completion_code("A", 1), "A001")
        self.assertEqual(MAX_AI_ROUNDS, 8)

    def test_labels(self):
        self.assertEqual(emotion_from_iv(0), "ingroup")
        self.assertEqual(emotion_from_iv(1), "outgroup")
        self.assertEqual(position_from_iv(0), "generic")
        self.assertEqual(position_from_iv(1), "contingent")
        self.assertTrue(is_ingroup("ingroup"))
        self.assertTrue(is_outgroup("outgroup"))
        self.assertTrue(is_generic_advice("generic"))
        self.assertTrue(is_contingent_advice("contingent"))

    def test_four_group_prompts_are_distinct(self):
        a_g = group_prompt_for("ingroup", "generic")
        a_c = group_prompt_for("ingroup", "contingent")
        b_g = group_prompt_for("outgroup", "generic")
        b_c = group_prompt_for("outgroup", "contingent")
        self.assertIn("A·支持用户 × 通用脚本", a_g)
        self.assertIn("A·支持用户 × 个性化", a_c)
        self.assertIn("B·反对用户 × 通用脚本", b_g)
        self.assertIn("B·反对用户 × 个性化", b_c)
        self.assertNotEqual(a_g, a_c)
        self.assertNotEqual(a_g, b_g)

    def test_opposition_prompts_require_direct_disagreement(self):
        generic = get_system_prompt("outgroup", "generic", ai_round=1)
        contingent = get_system_prompt("outgroup", "contingent")
        self.assertIn("直接反对硬约束", generic)
        self.assertIn("不得在反对立场前添加任何句子", generic)
        self.assertIn("直接且礼貌地表达与用户不同的判断", contingent)
        self.assertIn("禁止采用先肯定后转折的结构", contingent)

    def test_system_prompt_uses_group_block(self):
        prompt = get_system_prompt("ingroup", "generic")
        self.assertIn("A·支持用户 × 通用脚本", prompt)
        self.assertIn("不得在脚本前增加任何自由生成的承接句", prompt)
        self.assertIn("允许适度调整固定脚本内部的非关键词句表达", prompt)
        self.assertIn("保持共情、安慰和支持的风格", prompt)
        self.assertIn("不得针对、回应、暗示、引用或转述用户提到的具体内容", prompt)
        self.assertIn("不得根据用户输入内容调整", prompt)
        self.assertIn("第二段：", prompt)
        self.assertIn("同一行", prompt)
        self.assertNotIn("【本轮唯一追问点】", prompt)
        self.assertNotIn("【用户画像】", prompt)

    def test_contingent_includes_profile(self):
        prompt = get_system_prompt(
            "outgroup",
            "contingent",
            {"relationship_history": "认识三年", "key_quotes": ["他总是不回消息"]},
        )
        self.assertIn("B·反对用户 × 个性化", prompt)
        self.assertIn("【用户画像】", prompt)
        self.assertIn("认识三年", prompt)
        self.assertIn("【个性化建议字数约束】", prompt)
        self.assertIn("130–150", prompt)

    def test_contingent_captures_details_and_requires_paraphrase(self):
        prompt = get_system_prompt(
            "ingroup",
            "contingent",
            {
                "emotions_feelings": ["生气", "被忽视"],
                "interaction_details": ["对方连续三次没有回应"],
            },
        )
        self.assertIn("用户情绪与感受：生气；被忽视", prompt)
        self.assertIn("具体交往细节：对方连续三次没有回应", prompt)
        self.assertIn("【本轮转述开头】按你的描述，", prompt)
        self.assertIn("紧接【本轮语义摘要】", prompt)
        self.assertIn("必须且只能出现一次", prompt)
        self.assertIn("禁止逐字复制用户原句", prompt)
        self.assertIn("禁止使用引号包裹用户内容", prompt)
        self.assertIn("后来如何发展", prompt)

    def test_contingent_paraphrase_opener_varies_by_round(self):
        first = get_system_prompt("ingroup", "contingent", ai_round=1)
        second = get_system_prompt("ingroup", "contingent", ai_round=2)
        self.assertIn("【本轮转述开头】按你的描述，", first)
        self.assertIn("【本轮转述开头】从你刚才的表达来看，", second)

    def test_memory_cue_only_uses_paraphrased_turn_summary(self):
        profile = {
            "key_quotes": ["可能是他有空的时候，比如假期？但是平时不是会主动联系的朋友"],
            "current_turn_summary": "对方只在自己有空时联系用户",
        }
        self.assertEqual(memory_cue_from_profile(profile), "对方只在自己有空时联系用户")
        self.assertEqual(memory_cue_from_profile({}, "这句用户原文不能显示"), "")

    def test_profile_prompt_exposes_summary_but_not_raw_quotes(self):
        prompt = get_system_prompt(
            "ingroup",
            "contingent",
            {
                "current_turn_summary": "对方只在有空时联系用户",
                "key_quotes": ["这是一整句不应进入提示词的用户原文"],
            },
        )
        self.assertIn("本轮语义摘要：对方只在有空时联系用户", prompt)
        self.assertNotIn("这是一整句不应进入提示词的用户原文", prompt)

    def test_generic_omits_contingent_length_rule(self):
        prompt = get_system_prompt("ingroup", "generic")
        self.assertNotIn("【个性化建议字数约束】", prompt)

    def test_generic_uses_round_specific_script(self):
        first = get_system_prompt("ingroup", "generic", ai_round=1)
        eighth = get_system_prompt("outgroup", "generic", ai_round=8)
        self.assertIn("听起来确实是一件有点让人不舒服的事情", first)
        self.assertIn("**暂离冲突**", first)
        self.assertIn("第 8 轮", eighth)
        self.assertIn("这件事未必意味着对方应该承担主要责任", eighth)
        self.assertIn("**寻找误解**", eighth)

    def test_generic_starts_directly_with_fixed_script(self):
        ingroup = get_system_prompt("ingroup", "generic", ai_round=1)
        outgroup = get_system_prompt("outgroup", "generic", ai_round=1)
        self.assertIn("第一段必须直接从以上第一段脚本开始", ingroup)
        self.assertIn("不得在脚本前增加任何自由生成的承接句", ingroup)
        self.assertIn("允许对脚本内部的非关键词句做轻微措辞调整", ingroup)
        self.assertIn("ingroup 保持共情支持风格", ingroup)
        self.assertIn("第一段必须直接从以上第一段脚本开始", outgroup)
        self.assertIn("outgroup 保持客观反思风格", outgroup)
        self.assertNotIn("不超过15个汉字", ingroup)
        self.assertNotIn("通用对话式衔接", outgroup)

    def test_temperature_depends_on_advice_style(self):
        self.assertEqual(get_temperature("ingroup", 1, "generic"), 0.3)
        self.assertEqual(get_temperature("outgroup", 1, "generic"), 0.3)
        self.assertEqual(get_temperature("ingroup", 1, "contingent"), 0.3)
        self.assertEqual(get_temperature("outgroup", 1, "contingent"), 0.3)

    def test_shared_open_elicitation(self):
        g = get_system_prompt("ingroup", "generic", ai_round=1)
        c = get_system_prompt("outgroup", "contingent", ai_round=3)
        self.assertIn("同一行", g)
        self.assertIn("格式约束", g)
        self.assertIn("本轮固定追问】你愿意再多说一点当时发生了什么吗？", g)
        self.assertIn("不得改写、扩写", g)
        self.assertIn("同一行", c)
        self.assertIn("紧扣用户本轮已提到", c)
        self.assertNotIn("【本轮唯一追问点】", g)

    def test_generic_elicitation_follows_eight_fixed_questions(self):
        expected = (
            "你愿意再多说一点当时发生了什么吗？",
            "这件事情之后，你是怎么看待当时的情况的？",
            "这件事还有哪些部分是你比较在意的？",
            "你觉得这件事情对你们之间的相处有什么影响吗？",
            "关于这件事情，你还有什么想进一步聊聊的吗？",
            "你愿意说说后来事情是怎么发展的吗？",
            "现在回过头来看，你对这件事情有什么想法？",
            "除了刚才提到的这些，还有什么是你想说的吗？",
        )
        for round_number, question in enumerate(expected, start=1):
            prompt = get_system_prompt("outgroup", "generic", ai_round=round_number)
            self.assertIn(f"【本轮固定追问】{question}", prompt)


if __name__ == "__main__":
    unittest.main()
