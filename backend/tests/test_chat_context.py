import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ChatMessage, UserSession
from app.conditions import emotion_to_iv, position_to_iv
from app.services import (
    _build_chat_messages,
    _filter_outgroup_reply,
    _finalize_reply,
    _limit_advice_items,
    _limit_outgroup_analysis,
    _merge_late_question_paragraphs,
    _remove_late_advice_analysis,
    _reply_errors,
    _validated_reply,
)


class ChatContextTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_both_timing_groups_receive_full_history_without_profile(self):
        for advice in ("early_advice", "late_advice"):
            with self.subTest(advice=advice), self.Session() as db:
                code = "B001" if advice == "early_advice" else "B002"
                session = UserSession(
                    user_id=code,
                    completion_code=code,
                    emotion=emotion_to_iv("outgroup"),
                    position=position_to_iv(advice),
                    emotion_label="outgroup",
                    position_label=advice,
                    attempt_number=1,
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                db.add_all([
                    ChatMessage(session_id=session.id, role="user", content="他从不回我消息"),
                    ChatMessage(session_id=session.id, role="assistant", content="先分析一下。", round_number=1),
                    ChatMessage(session_id=session.id, role="user", content="我们认识三年了"),
                ])
                db.commit()

                messages = _build_chat_messages(db, session)
                self.assertEqual(len(messages), 6)
                self.assertNotIn("【用户画像】", messages[0]["content"])
                self.assertEqual(messages[1]["role"], "user")
                self.assertIn("主动反驳和挑战我的思考", messages[1]["content"])
                self.assertEqual(messages[2]["role"], "assistant")
                self.assertIn("指出推理漏洞", messages[2]["content"])
                self.assertEqual(messages[3]["content"], "他从不回我消息")
                self.assertEqual(messages[4]["role"], "assistant")
                self.assertEqual(messages[5]["content"], "我们认识三年了")

    def test_ingroup_messages_do_not_receive_challenge_injection(self):
        with self.Session() as db:
            session = UserSession(
                user_id="A001",
                completion_code="A001",
                emotion=emotion_to_iv("ingroup"),
                position=position_to_iv("early_advice"),
                emotion_label="ingroup",
                position_label="early_advice",
                attempt_number=1,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            db.add(ChatMessage(session_id=session.id, role="user", content="发生了冲突"))
            db.commit()
            messages = _build_chat_messages(db, session)
            self.assertEqual(len(messages), 2)
            self.assertNotIn("主动反驳和挑战我的思考", str(messages))

    def test_outgroup_filter_removes_alignment_but_preserves_challenge(self):
        filtered = "我不赞同这个判断，对方不一定做错了什么。"
        with patch("app.services._create_chat_completion", return_value=filtered) as completion:
            result = _filter_outgroup_reply(object(), "你的感受确实合理，但也可以换位思考。", 520)
        self.assertEqual(result, filtered)
        completion.assert_called_once()
        args = completion.call_args.args
        self.assertEqual(args[2], 0.5)
        self.assertIn("删除认可", args[1][0]["content"])
        self.assertIn("保留初稿中的challenge", args[1][0]["content"])
        self.assertIn("不得为了保持中立而弱化、删除或改写这些challenge", args[1][0]["content"])
        self.assertIn("你的感受确实合理", args[1][1]["content"])

    def test_outgroup_filter_failure_falls_back_to_draft(self):
        draft = "我不赞同这个判断，对方不一定做错了什么。"
        with patch("app.services._create_chat_completion", side_effect=ValueError("filter failed")):
            self.assertEqual(_filter_outgroup_reply(object(), draft, 520), draft)

    def test_stance_and_question_checks_do_not_include_length(self):
        session = UserSession(position_label="early_advice", emotion_label="ingroup", ai_round_count=0)
        unstructured = "这条回复没有分段，也没有使用项目符号。"
        self.assertEqual(len(_reply_errors(unstructured, session)), 4)
        self.assertNotIn("整轮超过400字", _reply_errors("甲" * 401, session))

    def test_outgroup_rejects_empathetic_alignment_and_requires_evaluation(self):
        session = UserSession(position_label="early_advice", emotion_label="outgroup", ai_round_count=0)
        errors = _reply_errors("我理解你的感受，我会支持你。", session)
        self.assertIn("outgroup立场出现了理解、认同或支持用户的结盟措辞", errors)
        self.assertIn("outgroup立场缺少责任不确定、其他解释或换位评估", errors)
        self.assertEqual(
            _reply_errors(
                "客观来看，我不赞同你当前的判断；目前无法判断责任归属，对方也可能有自己的道理。\n\n"
                "接下来可以尝试以下几种具体做法。\n\n"
                "- **建议一**：内容一\n- **建议二**：内容二\n- **建议三**：内容三\n\n"
                "我们可以继续聊聊这件事。",
                session,
            ),
            [],
        )

    def test_ingroup_requires_understanding_and_support(self):
        session = UserSession(position_label="early_advice", emotion_label="ingroup", ai_round_count=0)
        self.assertEqual(
            _reply_errors(
                "我理解你的感受，也会持续支持你。\n\n"
                "接下来可以尝试以下几种具体做法。\n\n"
                "- **建议一**：内容一\n- **建议二**：内容二\n- **建议三**：内容三\n\n"
                "你也可以继续分享任何你觉得重要的事情。",
                session,
            ),
            [],
        )

    def test_early_advice_requires_a_non_question_closing(self):
        session = UserSession(position_label="early_advice", emotion_label="outgroup", ai_round_count=0)
        reply = (
            "客观来看，我不赞同你当前的判断；目前无法判断责任归属，对方也可能有自己的道理。\n\n"
            "接下来可以尝试以下几种具体做法。\n\n"
            "- **建议一**：内容一\n- **建议二**：内容二\n- **建议三**：内容三\n\n"
            "如果你愿意，可以继续说说你的想法。"
        )
        self.assertEqual(_reply_errors(reply, session), [])
        self.assertIn(
            "early advice不得使用问句或问号",
            _reply_errors(reply + "你怎么看？", session),
        )

    def test_early_advice_requires_a_concrete_closing_after_bullets(self):
        session = UserSession(position_label="early_advice", emotion_label="ingroup", ai_round_count=0)
        without_closing = (
            "我理解你的感受，也会持续支持你。\n\n"
            "接下来可以尝试以下几种具体做法。\n\n"
            "- **建议一**：内容一\n- **建议二**：内容二\n- **建议三**：内容三"
        )
        self.assertIn(
            "early advice三条建议后必须另起一段提供具体的最后一步操作",
            _reply_errors(without_closing, session),
        )

    def test_early_advice_requires_exactly_three_suggestions(self):
        session = UserSession(position_label="early_advice", emotion_label="outgroup", ai_round_count=0)
        incomplete = (
            "我不赞同你当前的判断；目前无法判断责任归属，对方也可能有自己的道理。\n\n"
            "你愿意先尝试哪种做法？"
        )
        self.assertIn("意见阶段必须提供恰好三条项目符号建议", _reply_errors(incomplete, session))

    def test_late_advice_rounds_require_a_question_after_advice(self):
        session = UserSession(position_label="late_advice", emotion_label="outgroup", ai_round_count=4)
        base = "客观来看，我不赞同你当前的判断；目前无法判断责任归属，对方也可能有自己的道理。"
        self.assertIn("late advice意见阶段回复末尾必须有且只有一个自然的引导问题", _reply_errors(base, session))
        valid = (
            base
            + "\n\n接下来可以尝试以下几种具体做法。"
            + "\n\n- **建议一**：内容一\n- **建议二**：内容二\n- **建议三**：内容三"
            + "\n\n你觉得哪条建议最适合先尝试？"
        )
        self.assertEqual(_reply_errors(valid, session), [])

        session.ai_round_count = 3
        errors = _reply_errors(base, session)
        self.assertNotIn("late advice意见阶段回复末尾必须有且只有一个自然的引导问题", errors)
        self.assertIn("late advice前四轮必须围绕本轮主题提出恰好两个问题", errors)

    def test_advice_round_keeps_only_first_three_items_and_final_question(self):
        session = UserSession(position_label="late_advice", emotion_label="outgroup", ai_round_count=4)
        draft = (
            "我不赞同你当前的判断；目前无法判断责任归属，对方也可能有自己的道理。\n\n"
            "- **建议一**：内容一\n"
            "- **建议二**：内容二\n"
            "- **建议三**：内容三\n"
            "- **建议四**：内容四\n\n"
            "你觉得哪一条最适合先尝试？"
        )
        reply = _finalize_reply(draft, session)
        self.assertEqual(reply.count("- **建议"), 3)
        self.assertNotIn("建议四", reply)
        self.assertTrue(reply.endswith("你觉得哪一条最适合先尝试？"))

    def test_advice_limiter_leaves_three_or_fewer_items_unchanged(self):
        draft = "分析。\n\n- **建议一**：内容一\n- **建议二**：内容二\n\n继续聊聊吗？"
        self.assertEqual(_limit_advice_items(draft), draft)

    def test_late_advice_last_four_remove_extra_analysis_before_suggestions(self):
        session = UserSession(position_label="late_advice", emotion_label="ingroup", ai_round_count=4)
        draft = (
            "我理解你的感受，也会支持你的立场。你的期待是合理的。"
            "这份支持会一直持续。第四句不应保留。第五句也不应保留。\n\n"
            "从行为改变的角度看，还可以继续分析这段互动。这里是不需要的分析内容。\n\n"
            "接下来可以尝试以下几种具体做法。\n\n"
            "- **建议一**：内容一\n"
            "- **建议二**：内容二\n"
            "- **建议三**：内容三\n\n"
            "你愿意先尝试哪一条？"
        )
        result = _remove_late_advice_analysis(draft, session)
        self.assertIn("我理解你的感受", result)
        self.assertIn("这份支持会一直持续", result)
        self.assertNotIn("第四句不应保留", result)
        self.assertNotIn("第五句也不应保留", result)
        self.assertNotIn("从行为改变的角度", result)
        self.assertIn("接下来可以尝试以下几种具体做法", result)
        self.assertIn("- **建议一**", result)
        self.assertTrue(result.endswith("你愿意先尝试哪一条？"))

        session.position_label = "early_advice"
        self.assertEqual(_remove_late_advice_analysis(draft, session), draft)

    def test_outgroup_analysis_is_limited_to_four_sentences(self):
        draft = (
            "第一句。第二句。第三句。第四句。第五句。第六句。\n\n"
            "- **建议一**：内容一\n- **建议二**：内容二\n- **建议三**：内容三\n\n"
            "你愿意先试哪一条？"
        )
        result = _limit_outgroup_analysis(draft)
        self.assertIn("第一句。第二句。第三句。第四句。", result)
        self.assertNotIn("第五句", result)
        self.assertIn("- **建议三**：内容三", result)
        self.assertTrue(result.endswith("你愿意先试哪一条？"))

    def test_outgroup_alignment_is_detected_without_regex_deletion(self):
        raw = "你希望讨论停留在学术层面，这个期待本身合理，但仍需考虑对方的角度。"
        session = UserSession(position_label="late_advice", emotion_label="outgroup", ai_round_count=1)
        self.assertIn("outgroup立场出现了理解、认同或支持用户的结盟措辞", _reply_errors(raw, session))
        self.assertEqual(_finalize_reply(raw, session), raw)

    def test_failed_checks_without_rewriter_still_return_content(self):
        session = UserSession(position_label="late_advice", emotion_label="ingroup", ai_round_count=1)
        draft = "甲" * 301
        self.assertEqual(_validated_reply(draft, session), draft)

    def test_invalid_draft_is_rewritten_before_display(self):
        session = UserSession(position_label="late_advice", emotion_label="outgroup", ai_round_count=2)
        draft = "责任未明。" * 60
        revised = (
            "站在旁观者的角度来看，我不赞同你当前的判断；目前无法判断责任归属，还需要了解双方过去的互动。\n\n"
            "我对你们过去的互动还有些不太清楚，想再确认一下：你们过去通常如何沟通？发生分歧时通常由谁先开口？"
        )
        with patch("app.services._create_chat_completion", return_value=revised) as rewrite:
            reply = _validated_reply(draft, session, object(), [], 0.3, 520)
        self.assertEqual(reply, revised)
        self.assertEqual(_reply_errors(reply, session), [])
        rewrite.assert_called_once()

    def test_late_first_four_rounds_require_two_paragraphs_and_two_questions(self):
        session = UserSession(position_label="late_advice", emotion_label="outgroup", ai_round_count=1)
        base = "作为第三方，客观地看，我不赞同你当前的判断；目前无法判断责任归属，对方也可能有自己的道理。"
        valid = base + "\n\n我还有一点没有弄清楚，想确认一下：你当时是什么感受？你如何理解这种感受？"
        self.assertEqual(_reply_errors(valid, session), [])
        self.assertIn(
            "late advice前四轮必须围绕本轮主题提出恰好两个问题",
            _reply_errors(base + "\n\n我还有一点没有弄清楚，想确认一下：你当时是什么感受？", session),
        )
        self.assertIn(
            "late advice前四轮必须严格输出两个自然段",
            _reply_errors(base + "\n\n我还有一点没有弄清楚。\n\n你当时是什么感受？", session),
        )

    def test_late_first_four_merge_stance_and_analysis_into_first_paragraph(self):
        session = UserSession(position_label="late_advice", emotion_label="outgroup", ai_round_count=1)
        split_reply = (
            "我不赞同你当前的判断。\n\n"
            "目前信息不足以判断责任。对方也可能有自己的考虑。单一叙述不足以覆盖事情全貌。\n\n"
            "我可能还没有准确把握你当时的感受，想进一步了解：你当时最强烈的感受是什么？这种感受持续了多久？"
        )
        merged = _merge_late_question_paragraphs(split_reply, session)
        self.assertEqual(len(merged.split("\n\n")), 2)
        self.assertIn("我不赞同你当前的判断。目前信息不足", merged.split("\n\n")[0])
        self.assertTrue(merged.endswith("这种感受持续了多久？"))

    def test_late_first_four_merge_transition_and_question_into_second_paragraph(self):
        session = UserSession(position_label="late_advice", emotion_label="ingroup", ai_round_count=2)
        split_reply = (
            "我理解你的感受。你的情绪是可以接受的。这里还可以从互动模式理解。关系中的反应往往会相互影响。\n\n"
            "我对你们以往的互动了解有限。\n\n"
            "你们过去发生分歧时通常如何沟通？一般由谁先结束沉默？"
        )
        merged = _merge_late_question_paragraphs(split_reply, session)
        self.assertEqual(len(merged.split("\n\n")), 2)
        self.assertIn("互动了解有限。你们过去", merged.split("\n\n")[1])


if __name__ == "__main__":
    unittest.main()
