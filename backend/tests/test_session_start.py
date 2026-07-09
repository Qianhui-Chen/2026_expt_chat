import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import resolve_completion_code, start_anonymous_session
from app.models import UserSession
from app.conditions import emotion_to_iv, position_to_iv


class SessionStartTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_start_session_assigns_completion_code(self):
        with self.Session() as db:
            session, condition = start_anonymous_session(db)

        self.assertRegex(session.completion_code or "", r"^[AB]\d{3}$")
        self.assertEqual(session.user_id, session.completion_code)
        self.assertEqual(condition.user_id, session.completion_code)

    def test_code_matches_condition(self):
        with self.Session() as db:
            session, condition = start_anonymous_session(db)

        code = session.completion_code or ""
        number = int(code[1:])
        letter = code[0]

        if letter == "A":
            self.assertEqual(session.emotion, 0)
            self.assertEqual(condition.emotion, "anger")
            self.assertTrue(condition.is_anger)
        else:
            self.assertEqual(session.emotion, 1)
            self.assertEqual(condition.emotion, "neutral")
            self.assertFalse(condition.is_anger)

        if number % 2 == 1:
            self.assertEqual(session.position, 0)
            self.assertEqual(condition.position, "aligned")
        else:
            self.assertEqual(session.position, 1)
            self.assertEqual(condition.position, "ambiguous")

    def test_balanced_assignment_spreads_groups(self):
        with self.Session() as db:
            groups = set()
            for _ in range(8):
                session, condition = start_anonymous_session(db)
                groups.add((condition.emotion, condition.position))

        self.assertEqual(len(groups), 4)

    def test_resolve_completion_code_repairs_legacy_numeric_id(self):
        with self.Session() as db:
            session = UserSession(
                user_id="213",
                completion_code="213",
                emotion=emotion_to_iv("anger"),
                position=position_to_iv("aligned"),
                emotion_label="anger",
                position_label="aligned",
                attempt_number=1,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            code = resolve_completion_code(db, session)

        self.assertRegex(code, r"^A\d{3}$")
        self.assertEqual(int(code[1:]) % 2, 1)
        self.assertEqual(session.user_id, code)
        self.assertEqual(session.completion_code, code)


if __name__ == "__main__":
    unittest.main()
