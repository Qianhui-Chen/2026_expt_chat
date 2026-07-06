import json
import time
from collections.abc import Generator, Iterator
from datetime import datetime

from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI
from sqlalchemy.orm import Session

from app.conditions import (
    MAX_AI_ROUNDS,
    ConditionConfig,
    get_max_reply_tokens,
    get_system_prompt,
    get_temperature,
    parse_user_id,
)
from app.config import settings
from app.database import SessionLocal
from app.models import ChatMessage, UserSession

PLACEHOLDER_API_KEYS = frozenset(
    {
        "sk-your-key-here",
        "sk-your-deepseek-key-here",
        "your-api-key-here",
        "sk-xxx",
    }
)

MOCK_STREAM_CHAR_DELAY_SEC = 0.025


def _temperature_for_session(session: UserSession, ai_round: int) -> float:
    return get_temperature(session.emotion, ai_round)


def _llm_error_message(exc: Exception) -> str:
    if isinstance(exc, APIConnectionError):
        return "无法连接 DeepSeek 服务器，请检查网络连接或代理设置后重试。"
    if isinstance(exc, APITimeoutError):
        return "连接 DeepSeek 超时，请稍后重试。"
    if isinstance(exc, AuthenticationError):
        return "DeepSeek API Key 无效。请在 backend/.env 中设置正确的 DEEPSEEK_API_KEY 后重启后端。"
    if isinstance(exc, APIError):
        return f"DeepSeek 请求失败：{getattr(exc, 'message', None) or str(exc)}"
    return str(exc)


def _should_retry_with_alt_token_param(exc: APIError, token_key: str) -> bool:
    status_code = getattr(exc, "status_code", None)
    message = (getattr(exc, "message", None) or str(exc)).lower()
    return status_code == 400 and "unsupported" in message and token_key in message


def _is_llm_configured() -> bool:
    key = settings.deepseek_api_key.strip()
    return bool(key) and key not in PLACEHOLDER_API_KEYS


def _get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.deepseek_timeout_seconds,
    )


def _create_session(db: Session, condition: ConditionConfig, attempt_number: int) -> UserSession:
    session = UserSession(
        user_id=condition.user_id,
        emotion=condition.emotion,
        position=condition.position,
        attempt_number=attempt_number,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_or_create_session(db: Session, raw_user_id: str) -> tuple[UserSession, ConditionConfig]:
    condition = parse_user_id(raw_user_id)
    latest = (
        db.query(UserSession)
        .filter(UserSession.user_id == condition.user_id)
        .order_by(UserSession.attempt_number.desc(), UserSession.id.desc())
        .first()
    )
    if latest is None:
        return _create_session(db, condition, 1), condition
    if latest.experiment_finished:
        return _create_session(db, condition, latest.attempt_number + 1), condition
    return latest, condition


def get_session_by_token(db: Session, session_token: int) -> UserSession:
    session = db.query(UserSession).filter(UserSession.id == session_token).first()
    if session is None:
        raise ValueError("会话不存在，请重新登录")
    return session


def list_chat_messages(db: Session, session: UserSession) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.timestamp.asc(), ChatMessage.id.asc())
        .all()
    )


def save_user_message(db: Session, session: UserSession, message: str) -> ChatMessage:
    if session.chat_finished:
        raise ValueError("聊天已结束")

    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=message.strip(),
        round_number=None,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    return user_msg


def finalize_assistant_message(
    db: Session, session: UserSession, content: str
) -> tuple[ChatMessage, bool]:
    next_round = session.ai_round_count + 1
    ai_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=content.strip(),
        round_number=next_round,
    )
    session.ai_round_count = next_round
    finished = next_round >= MAX_AI_ROUNDS
    if finished:
        session.chat_finished = 1

    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    db.refresh(session)
    return ai_msg, finished


def mark_chat_finished(db: Session, session: UserSession) -> None:
    session.chat_finished = 1
    db.commit()


def complete_experiment(db: Session, session: UserSession) -> UserSession:
    session.experiment_finished = 1
    if session.exit_reason is None:
        session.exit_reason = "completed"
    db.commit()
    db.refresh(session)
    return session


def record_instruction_screening(
    db: Session, session: UserSession, has_similar_experience: bool
) -> bool:
    if session.has_similar_experience is not None:
        return bool(session.has_similar_experience)
    if session.experiment_finished:
        raise ValueError("实验已结束")

    session.has_similar_experience = 1 if has_similar_experience else 0

    if has_similar_experience:
        db.commit()
        db.refresh(session)
        return True

    session.chat_finished = 1
    session.experiment_finished = 1
    session.exit_reason = "no_similar_experience"
    db.commit()
    db.refresh(session)
    return False


def send_user_message(db: Session, session: UserSession, message: str) -> tuple[ChatMessage, ChatMessage | None, bool]:
    user_msg = save_user_message(db, session, message)

    if session.ai_round_count >= MAX_AI_ROUNDS:
        mark_chat_finished(db, session)
        return user_msg, None, True

    ai_content = _generate_ai_reply(db, session)
    ai_msg, finished = finalize_assistant_message(db, session, ai_content)
    return user_msg, ai_msg, finished


def _build_chat_messages(db: Session, session: UserSession) -> list[dict[str, str]]:
    history = list_chat_messages(db, session)
    condition = parse_user_id(session.user_id)
    next_round = session.ai_round_count + 1
    system_prompt = get_system_prompt(condition.emotion, condition.position, next_round)
    messages = [{"role": "system", "content": system_prompt}]
    for item in history:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content})
    return messages


def _stream_llm_tokens(
    messages: list[dict[str, str]], temperature: float, max_tokens: int
) -> Iterator[str]:
    client = _get_llm_client()
    base_kwargs: dict = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    for token_key in ("max_completion_tokens", "max_tokens"):
        kwargs = {**base_kwargs, token_key: max_tokens}
        try:
            stream = client.chat.completions.create(**kwargs)
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return
        except APIError as exc:
            if _should_retry_with_alt_token_param(exc, token_key):
                continue
            raise

    raise ValueError("DeepSeek 请求失败：当前模型不支持已知的 token 限制参数。")


def _stream_mock_tokens(session: UserSession) -> Iterator[str]:
    text = _mock_ai_reply(session)
    for char in text:
        time.sleep(MOCK_STREAM_CHAR_DELAY_SEC)
        yield char


def stream_ai_reply_tokens(db: Session, session: UserSession) -> Iterator[str]:
    if not _is_llm_configured():
        yield from _stream_mock_tokens(session)
        return

    messages = _build_chat_messages(db, session)
    next_round = session.ai_round_count + 1
    temperature = _temperature_for_session(session, next_round)
    max_tokens = get_max_reply_tokens(next_round)
    try:
        yield from _stream_llm_tokens(messages, temperature, max_tokens)
    except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
        raise ValueError(_llm_error_message(exc)) from exc


def _create_chat_completion(
    client: OpenAI,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    base_kwargs: dict = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": temperature,
    }

    for token_key in ("max_completion_tokens", "max_tokens"):
        kwargs = {**base_kwargs, token_key: max_tokens}
        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if not content:
                raise ValueError("DeepSeek 返回了空回复")
            return content.strip()
        except APIError as exc:
            if _should_retry_with_alt_token_param(exc, token_key):
                continue
            raise

    raise ValueError("DeepSeek 请求失败：当前模型不支持已知的 token 限制参数。")


def _generate_ai_reply(db: Session, session: UserSession) -> str:
    if not _is_llm_configured():
        return _mock_ai_reply(session)

    messages = _build_chat_messages(db, session)
    client = _get_llm_client()
    next_round = session.ai_round_count + 1
    temperature = _temperature_for_session(session, next_round)
    max_tokens = get_max_reply_tokens(next_round)

    try:
        return _create_chat_completion(client, messages, temperature, max_tokens)
    except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
        raise ValueError(_llm_error_message(exc)) from exc


def _mock_ai_reply(session: UserSession) -> str:
    round_no = session.ai_round_count + 1
    if session.emotion == "anger":
        return f"这确实太不公平了！（第{round_no}轮模拟回复，请配置 DEEPSEEK_API_KEY 以启用真实对话。）"
    return f"我理解你的感受，我们可以慢慢聊聊。（第{round_no}轮模拟回复，请配置 DEEPSEEK_API_KEY 以启用真实对话。）"


def _message_to_dict(msg: ChatMessage) -> dict:
    return {
        "role": msg.role,
        "content": msg.content,
        "round_number": msg.round_number,
        "timestamp": msg.timestamp.isoformat(),
    }


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_chat_events(session_token: int, message: str) -> Generator[str, None, None]:
    db = SessionLocal()
    try:
        session = get_session_by_token(db, session_token)
        condition = parse_user_id(session.user_id)
        user_msg = save_user_message(db, session, message)
        yield _sse_event("user_message", _message_to_dict(user_msg))

        if session.ai_round_count >= MAX_AI_ROUNDS:
            mark_chat_finished(db, session)
            yield _sse_event(
                "done",
                {
                    "ai_message": None,
                    "ai_round_count": session.ai_round_count,
                    "chat_finished": True,
                    "is_anger": condition.is_anger,
                },
            )
            return

        yield _sse_event("thinking", {"message": "AI 正在思考…"})

        parts: list[str] = []
        for token in stream_ai_reply_tokens(db, session):
            parts.append(token)
            yield _sse_event("token", {"delta": token})

        full_content = "".join(parts).strip()
        if not full_content:
            raise ValueError("DeepSeek 返回了空回复")

        ai_msg, finished = finalize_assistant_message(db, session, full_content)
        yield _sse_event(
            "done",
            {
                "ai_message": _message_to_dict(ai_msg),
                "ai_round_count": session.ai_round_count,
                "chat_finished": finished,
                "is_anger": condition.is_anger,
            },
        )
    except ValueError as exc:
        yield _sse_event("error", {"message": str(exc)})
    except Exception as exc:
        yield _sse_event("error", {"message": f"聊天服务异常：{exc}"})
    finally:
        db.close()
