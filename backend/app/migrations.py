from sqlalchemy import inspect, text

from app.database import engine


def _table_columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _sqlite_user_id_has_solo_unique(conn) -> bool:
    rows = conn.execute(text("PRAGMA index_list('user_sessions')")).fetchall()
    for row in rows:
        if not row[2]:
            continue
        index_name = row[1]
        info = conn.execute(text(f"PRAGMA index_info('{index_name}')")).fetchall()
        if [item[2] for item in info] == ["user_id"]:
            return True
    return False


def _rebuild_user_sessions_sqlite(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE user_sessions_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR(32) NOT NULL,
                emotion VARCHAR(16) NOT NULL,
                position VARCHAR(16) NOT NULL,
                ai_round_count INTEGER NOT NULL DEFAULT 0,
                chat_finished INTEGER NOT NULL DEFAULT 0,
                attempt_number INTEGER NOT NULL DEFAULT 1,
                experiment_finished INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                CONSTRAINT uq_user_attempt UNIQUE (user_id, attempt_number)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO user_sessions_new (
                id, user_id, emotion, position, ai_round_count, chat_finished,
                attempt_number, experiment_finished, created_at
            )
            SELECT
                id, user_id, emotion, position, ai_round_count, chat_finished,
                1, 0, created_at
            FROM user_sessions
            """
        )
    )
    conn.execute(text("DROP TABLE user_sessions"))
    conn.execute(text("ALTER TABLE user_sessions_new RENAME TO user_sessions"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_sessions_id ON user_sessions (id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions (user_id)"))


def _postgres_has_composite_unique(conn) -> bool:
    inspector = inspect(conn)
    for constraint in inspector.get_unique_constraints("user_sessions"):
        if (constraint.get("column_names") or []) == ["user_id", "attempt_number"]:
            return True
    for index in inspector.get_indexes("user_sessions"):
        if index.get("unique") and (index.get("column_names") or []) == [
            "user_id",
            "attempt_number",
        ]:
            return True
    return False


def _drop_postgres_solo_user_id_unique(conn, inspector) -> None:
    for constraint in inspector.get_unique_constraints("user_sessions"):
        if (constraint.get("column_names") or []) == ["user_id"]:
            name = constraint["name"]
            conn.execute(text(f'ALTER TABLE user_sessions DROP CONSTRAINT IF EXISTS "{name}"'))

    for index in inspector.get_indexes("user_sessions"):
        if not index.get("unique"):
            continue
        if (index.get("column_names") or []) == ["user_id"]:
            name = index["name"]
            conn.execute(text(f'DROP INDEX IF EXISTS "{name}"'))


def _migrate_postgres_user_sessions(conn, inspector) -> None:
    _drop_postgres_solo_user_id_unique(conn, inspector)

    if not _postgres_has_composite_unique(conn):
        conn.execute(
            text(
                "ALTER TABLE user_sessions ADD CONSTRAINT uq_user_attempt UNIQUE (user_id, attempt_number)"
            )
        )

    refreshed = inspect(conn)
    index_names = {index["name"] for index in refreshed.get_indexes("user_sessions")}
    if "ix_user_sessions_user_id" not in index_names:
        conn.execute(text("CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id)"))


def run_migrations() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("user_sessions"):
        return

    columns = _table_columns(inspector, "user_sessions")
    dialect = engine.dialect.name

    with engine.begin() as conn:
        if "attempt_number" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE user_sessions ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 1"
                )
            )
        if "experiment_finished" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE user_sessions ADD COLUMN experiment_finished INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "has_similar_experience" not in columns:
            conn.execute(
                text("ALTER TABLE user_sessions ADD COLUMN has_similar_experience INTEGER")
            )
        if "exit_reason" not in columns:
            conn.execute(text("ALTER TABLE user_sessions ADD COLUMN exit_reason VARCHAR(64)"))

        if dialect == "sqlite":
            if _sqlite_user_id_has_solo_unique(conn):
                _rebuild_user_sessions_sqlite(conn)
        elif dialect == "postgresql":
            _migrate_postgres_user_sessions(conn, inspector)
