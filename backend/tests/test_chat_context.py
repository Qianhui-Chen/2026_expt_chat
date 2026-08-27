import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ChatMessage, UserSession
from app.conditions import emotion_to_iv, position_to_iv
from app.services import (
    _build_chat_messages,
    _enforce_contingent_advice_length,
    _ensure_advice_bullets,
    _dedupe_paraphrase_leads,
    _replace_verbatim_user_quotes,
)


class ChatContextTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _session(self, db, *, emotion: str, advice: str, profile: str | None = None) -> UserSession:
        session = UserSession(
            user_id="A001" if advice == "generic" else "A002",
            completion_code="A001" if advice == "generic" else "A002",
            emotion=emotion_to_iv(emotion),
            position=position_to_iv(advice),
            emotion_label=emotion,
            position_label=advice,
            attempt_number=1,
            user_profile=profile,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        db.add_all(
            [
                ChatMessage(session_id=session.id, role="user", content="他从不回我消息"),
                ChatMessage(session_id=session.id, role="assistant", content="先分析一下。", round_number=1),
                ChatMessage(session_id=session.id, role="user", content="我们认识三年了"),
            ]
        )
        db.commit()
        db.refresh(session)
        return session

    def test_generic_generation_does_not_receive_user_content(self):
        with self.Session() as db:
            session = self._session(db, emotion="ingroup", advice="generic")
            messages = _build_chat_messages(db, session)

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(
            messages[1],
            {"role": "user", "content": "请按系统提示输出本轮通用回复。"},
        )
        self.assertNotIn("我们认识三年了", str(messages))
        self.assertNotIn("他从不回我消息", str(messages))
        self.assertIn("A·支持用户 × 通用脚本", messages[0]["content"])
        self.assertIn("通用对话式衔接", messages[0]["content"])
        self.assertNotIn("【用户画像】", messages[0]["content"])

    def test_contingent_sends_full_history_and_profile(self):
        with self.Session() as db:
            session = self._session(
                db,
                emotion="outgroup",
                advice="contingent",
                profile='{"relationship_history":"认识三年","key_quotes":["他从不回我消息"]}',
            )
            messages = _build_chat_messages(db, session)

        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("【用户画像】", messages[0]["content"])
        self.assertIn("认识三年", messages[0]["content"])
        self.assertNotIn("用户性格", messages[0]["content"])
        self.assertNotIn("对方性格", messages[0]["content"])
        self.assertNotIn("语言表达习惯", messages[0]["content"])
        self.assertIn("B·反对用户 × 个性化", messages[0]["content"])
        self.assertIn("必须依据【用户画像】", messages[0]["content"])
        self.assertEqual(messages[1]["content"], "他从不回我消息")
        self.assertEqual(messages[2]["role"], "assistant")
        self.assertEqual(messages[3]["content"], "我们认识三年了")

    def test_generic_advice_forces_bullets_and_bold_titles(self):
        raw = (
            "这是一段立场回应。\n\n"
            "暂离冲突：先暂时离开。\n"
            "• **保持距离**：与事件拉开距离。\n"
            "3. 冷静观察: 再决定如何回应。\n\n"
            "你愿意再讲讲吗？"
        )
        formatted = _ensure_advice_bullets(raw)
        self.assertIn("- **暂离冲突**：先暂时离开。", formatted)
        self.assertIn("- **保持距离**：与事件拉开距离。", formatted)
        self.assertIn("- **冷静观察**：再决定如何回应。", formatted)

    def test_contingent_advice_is_capped_at_150_chars(self):
        long_advice = "这是需要压缩的个性化建议，" * 30
        formatted = _enforce_contingent_advice_length(
            f"这是立场回应。\n\n{long_advice}\n\n你愿意再说说吗？"
        )
        parts = formatted.split("\n\n")
        self.assertEqual(len(parts), 3)
        self.assertLessEqual(len(parts[1]), 150)
        self.assertTrue(parts[1].endswith("。"))

    def test_verbatim_user_quote_is_replaced_with_summary(self):
        original = "可能是他有空的时候，比如假期？但是平时不是会主动联系的朋友"
        reply = f"你提到“{original}”，这确实会让人失望。"
        rewritten = _replace_verbatim_user_quotes(
            reply, original, "对方只在自己有空时联系你"
        )
        self.assertEqual(rewritten, "你提到对方只在自己有空时联系你，这确实会让人失望。")
        self.assertNotIn(original, rewritten)

    def test_duplicate_paraphrase_leads_are_collapsed(self):
        reply = (
            "你提到假期时朋友表现正常且会提前约，"
            "我听见你说假期时朋友表现正常且会提前约。这确实让人困惑。"
        )
        rewritten = _dedupe_paraphrase_leads(reply)
        self.assertEqual(rewritten, "你提到假期时朋友表现正常且会提前约，这确实让人困惑。")
        self.assertNotIn("我听见你说", rewritten)



if __name__ == "__main__":
    unittest.main()
