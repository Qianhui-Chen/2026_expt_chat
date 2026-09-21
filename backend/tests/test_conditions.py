import unittest

from app.conditions import (
    MAX_AI_ROUNDS,
    MAX_REPLY_CHARS,
    advice_topic_indices,
    format_completion_code,
    get_system_prompt,
    group_prompt_for,
    emotion_from_iv,
    position_from_iv,
    position_to_iv,
)


class ConditionTests(unittest.TestCase):
    def test_assignment_labels_and_parity(self):
        self.assertEqual(MAX_AI_ROUNDS, 8)
        self.assertEqual(MAX_REPLY_CHARS, 400)
        self.assertEqual(format_completion_code("A", 1), "A001")
        self.assertEqual(emotion_from_iv(0), "ingroup")
        self.assertEqual(emotion_from_iv(1), "outgroup")
        self.assertEqual(position_from_iv(0), "early_advice")
        self.assertEqual(position_from_iv(1), "late_advice")
        self.assertEqual(position_to_iv("early_advice"), 0)
        self.assertEqual(position_to_iv("late_advice"), 1)

    def test_stance_is_same_across_advice_timing(self):
        for emotion in ("ingroup", "outgroup"):
            self.assertEqual(
                group_prompt_for(emotion, "early_advice"),
                group_prompt_for(emotion, "late_advice"),
            )
        self.assertIn("用户的情绪是合理且可以接受的", group_prompt_for("ingroup", "early_advice"))
        self.assertIn("对方不一定做错了什么", group_prompt_for("outgroup", "late_advice"))
        self.assertIn("对方的角度", group_prompt_for("outgroup", "early_advice"))
        self.assertIn("不要先认可、安慰、支持或复述用户", group_prompt_for("outgroup", "early_advice"))
        self.assertIn("用户的描述只是单方信息", group_prompt_for("outgroup", "early_advice"))
        self.assertIn("不得使用“你凭什么”", group_prompt_for("outgroup", "early_advice"))
        self.assertIn("立场表达控制在2–3句话", group_prompt_for("ingroup", "early_advice"))
        self.assertIn("立场表达控制在2–3句话", group_prompt_for("outgroup", "early_advice"))

    def test_early_advice_uses_one_topic_and_three_bullets_each_round(self):
        for emotion in ("ingroup", "outgroup"):
            for round_number in range(1, 9):
                prompt = get_system_prompt(emotion, "early_advice", ai_round=round_number)
                self.assertEqual(advice_topic_indices("early_advice", round_number), (round_number - 1,))
                self.assertIn(f"Topic {round_number}：", prompt)
                self.assertIn("恰好3条具体建议", prompt)
                self.assertIn("- **小标题**：建议内容", prompt)
                self.assertIn("第一段只按本组立场回应，控制在2–3句话", prompt)
                self.assertIn("不额外展开分析", prompt)
                self.assertIn("第一条建议之前另起一段", prompt)
                self.assertIn("一些可操作的方法或意见", prompt)
                self.assertIn("不要机械重复固定模板", prompt)
                self.assertNotIn("整轮回复末尾另起一行加入一个自然的引导问题", prompt)
                self.assertNotIn("只问一个核心问题", prompt)
                self.assertIn("三条建议之后必须再单独输出一句结语", prompt)
                self.assertIn("结语应像针对当前情境给出的最后一步操作", prompt)
                self.assertIn("可以直接使用的话术", prompt)
                self.assertIn("明确到时间、场景或行为的下一步", prompt)
                self.assertIn("避免只写", prompt)
                self.assertIn("这句结语不得邀请用户继续分享", prompt)
                self.assertIn("不得提出问题或使用问号", prompt)
                self.assertNotIn("分析＋引导问题", prompt)

    def test_outgroup_uses_a_different_perspective_opening_each_round(self):
        openings = []
        for round_number in range(1, 9):
            prompt = get_system_prompt("outgroup", "early_advice", ai_round=round_number)
            marker = "本轮优先使用“"
            start = prompt.index(marker) + len(marker)
            opening = prompt[start:prompt.index("”作为视角开头", start)]
            openings.append(opening)
            self.assertIn("必须保留第三方、外部、旁观者、局外人或客观观察的视角含义", prompt)
        self.assertEqual(len(set(openings)), 8)

    def test_late_advice_first_four_topics_then_placeholder(self):
        topics = ("背景", "感受、情绪和解释", "过往的互动经历", "性格、沟通习惯和偏好")
        for emotion in ("ingroup", "outgroup"):
            for round_number, topic in enumerate(topics, start=1):
                prompt = get_system_prompt(emotion, "late_advice", ai_round=round_number)
                self.assertIn(topic, prompt)
                self.assertIn("不提供解决意见", prompt)
                self.assertIn("第一段将本组立场和分析合并写成一个自然段，共3-4句话", prompt)
                self.assertIn("立场与分析之间不得换行或留出空行", prompt)
                self.assertIn("客观、有说服力且有见地", prompt)
                self.assertIn("提出2个引导问题", prompt)
                self.assertIn("恰好出现两个问题和两个问号", prompt)
                self.assertIn("本轮唯一主题", prompt)
                self.assertIn("本轮主题下不同的子问题", prompt)
                self.assertIn("不得涉及其他轮次的主题", prompt)
                self.assertIn("不要逐字复述主题说明", prompt)
                self.assertIn("过渡语和问题之间不得换段", prompt)
                self.assertIn("严格输出两个自然段", prompt)
                self.assertIn("这只是含义方向", prompt)
                self.assertIn("不得逐字复述", prompt)
                self.assertIn("不要沿用前几轮已经使用过的过渡句", prompt)
                self.assertIn("我对事情还有一些不太明白的地方，想再确认一个细节", prompt)
                self.assertIn("可以使用", prompt)
                self.assertIn("同一会话中不要连续使用", prompt)
                self.assertNotIn("恰好4条具体建议", prompt)
                self.assertIn("自然、谦逊的过渡语", prompt)
            for round_number in range(5, 9):
                prompt = get_system_prompt(emotion, "late_advice", ai_round=round_number)
                first, second = advice_topic_indices("late_advice", round_number)
                self.assertIn(f"Topic {first + 1}：", prompt)
                self.assertIn(f"Topic {second + 1}：", prompt)
                self.assertIn("恰好3条具体建议", prompt)
                self.assertIn("第一段只按本组立场回应，控制在2–3句话", prompt)
                self.assertIn("不要生成独立分析段", prompt)
                self.assertIn("第一条建议之前另起一段", prompt)
                self.assertIn("一些可操作的方法或意见", prompt)
                self.assertIn("三条建议整体覆盖本轮的两个主题", prompt)
                self.assertIn("先回顾完整对话", prompt)
                self.assertIn("此前已经问过的问题", prompt)
                self.assertIn("优先承接用户最近表述中的具体信息", prompt)
                self.assertIn("简短假设场景", prompt)
                self.assertIn("进一步表达感受和情绪", prompt)
                self.assertIn("继续分享尚未展开的具体细节", prompt)
                self.assertIn("引导用户反思", prompt)
                self.assertIn("不必全部使用", prompt)
                self.assertIn("不要为了覆盖多种方式而把问题写得复杂臃肿", prompt)
                self.assertIn("只问一个简短、清楚的核心问题", prompt)
                self.assertIn("不得把此前的问题换成近义说法重新询问", prompt)
                self.assertIn("不得先长篇铺垫再提问", prompt)
                self.assertIn("不得在一个问句中并列多个问题", prompt)

    def test_all_groups_and_rounds_have_total_reply_limit(self):
        for emotion in ("ingroup", "outgroup"):
            for timing in ("early_advice", "late_advice"):
                for round_number in range(1, 9):
                    prompt = get_system_prompt(emotion, timing, ai_round=round_number)
                    self.assertIn("通常控制在180–280字", prompt)
                    self.assertIn("不得超过400字", prompt)


if __name__ == "__main__":
    unittest.main()
