import json
import random
import re
import time
from collections.abc import Generator, Iterator

from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI
from sqlalchemy.orm import Session

from app.conditions import (
    ADVICE_MAX_CHARS,
    ADVICE_MIN_CHARS,
    COMPLETION_CODE_MAX,
    MAX_AI_ROUNDS,
    ConditionConfig,
    condition_from_session,
    emotion_to_iv,
    format_completion_code,
    get_max_reply_tokens,
    get_system_prompt,
    get_temperature,
    is_contingent_advice,
    is_generic_advice,
    is_ingroup,
    memory_cue_from_profile,
    position_to_iv,
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

_COMPLETION_CODE_RE = re.compile(r"^[AB]\d{3}$")

_CONDITION_GROUPS: tuple[tuple[str, str, str, bool], ...] = (
    ("ingroup", "generic", "A", True),
    ("ingroup", "contingent", "A", False),
    ("outgroup", "generic", "B", True),
    ("outgroup", "contingent", "B", False),
)

_MEMORY_EXTRACT_SYSTEM = (
    "你是实验用的用户画像抽取器。只输出 JSON 对象，不要 markdown，不要解释。"
    "字段固定为："
        '{"emotions_feelings":[],"interaction_details":[],'
        '"relationship_history":"","key_quotes":[],'
        '"current_turn_summary":""}'
    "规则：只根据对话中明确出现的信息更新；不要编造；上一轮仍有效的内容保留；"
    "首要提取用户在情境中的具体情绪和感受，以及具体交往细节，包括发生了什么、双方说了什么或做了什么、"
    "对方如何回应、事情如何发展；其次提取用户与对方的交往历史；"
    "emotions_feelings 和 interaction_details 应尽量保留明确、具体的信息，不要抽象成空泛标签；"
    "key_quotes 最多 8 条，尽量摘录用户原话。"
    "current_turn_summary 只概括本轮发言的核心含义，控制在 22 个汉字以内；必须自然改写，"
    "不得逐字复制本轮原句，不得改变原意或补充用户未表达的信息。"
)

_MEMORY_EXTRACT_MAX_TOKENS = 400
_MEMORY_EXTRACT_TEMPERATURE = 0.2


def session_condition(session: UserSession) -> ConditionConfig:
    code = session.completion_code or session.user_id
    return condition_from_session(
        completion_code=code,
        emotion_iv=session.emotion,
        position_iv=session.position,
    )


def _parse_code_number(code: str, letter: str) -> int | None:
    if not code or len(code) != 4 or code[0] != letter:
        return None
    try:
        return int(code[1:])
    except ValueError:
        return None


def _used_numbers_for_letter_parity(db: Session, letter: str, want_odd: bool) -> set[int]:
    rows = (
        db.query(UserSession.completion_code, UserSession.user_id)
        .filter(
            (UserSession.completion_code.like(f"{letter}%"))
            | (UserSession.user_id.like(f"{letter}%"))
        )
        .all()
    )
    used: set[int] = set()
    for completion_code, user_id in rows:
        for code in (completion_code, user_id):
            number = _parse_code_number(code or "", letter)
            if number is None:
                continue
            if (number % 2 == 1) == want_odd:
                used.add(number)
    return used


def _next_code_number(want_odd: bool, used: set[int]) -> int:
    number = 1 if want_odd else 2
    while number <= COMPLETION_CODE_MAX:
        if number not in used:
            return number
        number += 2
    raise ValueError("该组完成代码已用完")


def _pick_balanced_condition(db: Session) -> tuple[str, str, str, bool]:
    counts: dict[tuple[str, str], int] = {}
    for emotion_label, position_label, _, _ in _CONDITION_GROUPS:
        key = (emotion_label, position_label)
        counts[key] = (
            db.query(UserSession)
            .filter(
                UserSession.emotion_label == emotion_label,
                UserSession.position_label == position_label,
            )
            .count()
        )
    min_count = min(counts.values())
    candidates = [key for key, count in counts.items() if count == min_count]
    emotion, position = random.choice(candidates)
    for group_emotion, group_position, letter, want_odd in _CONDITION_GROUPS:
        if group_emotion == emotion and group_position == position:
            return emotion, position, letter, want_odd
    raise ValueError("无法分配实验条件")


def resolve_completion_code(db: Session, session: UserSession) -> str:
    """返回 A001 格式完成代码；旧纯数字记录会按分组规则补全。"""
    for candidate in (session.completion_code, session.user_id):
        if candidate and _COMPLETION_CODE_RE.match(candidate):
            if session.completion_code != candidate or session.user_id != candidate:
                session.completion_code = candidate
                session.user_id = candidate
                db.commit()
                db.refresh(session)
            return candidate

    letter = "A" if is_ingroup(session.emotion_label) else "B"
    want_odd = is_generic_advice(session.position_label)
    used = _used_numbers_for_letter_parity(db, letter, want_odd)
    number = _next_code_number(want_odd, used)
    code = format_completion_code(letter, number)
    session.completion_code = code
    session.user_id = code
    db.commit()
    db.refresh(session)
    return code


def start_anonymous_session(db: Session) -> tuple[UserSession, ConditionConfig]:
    emotion_label, position_label, letter, want_odd = _pick_balanced_condition(db)
    used = _used_numbers_for_letter_parity(db, letter, want_odd)
    number = _next_code_number(want_odd, used)
    completion_code = format_completion_code(letter, number)

    session = UserSession(
        user_id=completion_code,
        completion_code=completion_code,
        emotion=emotion_to_iv(emotion_label),
        position=position_to_iv(position_label),
        emotion_label=emotion_label,
        position_label=position_label,
        attempt_number=1,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, session_condition(session)


def _temperature_for_session(session: UserSession, ai_round: int) -> float:
    return get_temperature(session.emotion_label, ai_round, session.position_label)


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


def get_session_by_token(db: Session, session_token: int) -> UserSession:
    session = db.query(UserSession).filter(UserSession.id == session_token).first()
    if session is None:
        raise ValueError("会话不存在，请重新开始实验")
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


def send_user_message(db: Session, session: UserSession, message: str) -> tuple[ChatMessage, ChatMessage | None, bool]:
    user_msg = save_user_message(db, session, message)

    if session.ai_round_count >= MAX_AI_ROUNDS:
        mark_chat_finished(db, session)
        return user_msg, None, True

    if is_contingent_advice(session.position_label):
        _refresh_user_profile(db, session)
    ai_content = _generate_ai_reply(db, session)
    if is_contingent_advice(session.position_label):
        ai_content = _replace_verbatim_user_quotes(
            ai_content,
            user_msg.content,
            memory_cue_from_profile(session.user_profile),
        )
        ai_content = _dedupe_paraphrase_leads(ai_content)
    ai_msg, finished = finalize_assistant_message(db, session, ai_content)
    return user_msg, ai_msg, finished


def _build_chat_messages(db: Session, session: UserSession) -> list[dict[str, str]]:
    history = list_chat_messages(db, session)
    advice_style = session.position_label
    profile = session.user_profile if is_contingent_advice(advice_style) else None
    next_round = session.ai_round_count + 1
    system_prompt = get_system_prompt(
        session.emotion_label,
        advice_style,
        profile,
        ai_round=next_round,
    )
    messages = [{"role": "system", "content": system_prompt}]

    if is_generic_advice(advice_style):
        messages.append({"role": "user", "content": "请按系统提示输出本轮通用回复。"})
        return messages

    for item in history:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content})
    return messages


def _latest_user_content(history: list[ChatMessage]) -> str:
    for item in reversed(history):
        if item.role == "user":
            return item.content
    return ""


def _parse_profile_json(raw: str) -> dict | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _replace_verbatim_user_quotes(content: str, user_text: str, summary: str) -> str:
    """兜底替换模型对本轮原句的带引号摘抄，确保 contingent 使用语义转述。"""
    if not content or not user_text or not summary:
        return content
    normalized_user = " ".join(user_text.split())
    quote_pattern = re.compile(r"[“\"]([^”\"]{4,})[”\"]")

    def replace(match: re.Match[str]) -> str:
        quoted = " ".join(match.group(1).split())
        if quoted in normalized_user:
            return summary
        return match.group(0)

    return quote_pattern.sub(replace, content)


def _dedupe_paraphrase_leads(content: str) -> str:
    """contingent 回复只保留首个「你提到/我听见你说」承接分句。"""
    pattern = re.compile(r"(?:你提到|我听见你说)[^，。！？；\n]*[，。！？；]?")
    seen = False

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        if not seen:
            seen = True
            return match.group(0)
        return ""

    cleaned = pattern.sub(replace, content)
    return re.sub(r"([，。！？；])\1+", r"\1", cleaned)


def _refresh_user_profile(db: Session, session: UserSession) -> None:
    if not is_contingent_advice(session.position_label):
        return
    if not _is_llm_configured():
        return

    history = list_chat_messages(db, session)
    latest_user = _latest_user_content(history)
    if not latest_user:
        return

    previous = session.user_profile or "{}"
    user_payload = (
        f"上一轮用户画像 JSON：\n{previous}\n\n"
        f"用户本轮发言：\n{latest_user}\n\n"
        "请输出更新后的完整 JSON。"
    )
    extract_messages = [
        {"role": "system", "content": _MEMORY_EXTRACT_SYSTEM},
        {"role": "user", "content": user_payload},
    ]
    try:
        client = _get_llm_client()
        raw = _create_chat_completion(
            client,
            extract_messages,
            _MEMORY_EXTRACT_TEMPERATURE,
            _MEMORY_EXTRACT_MAX_TOKENS,
        )
        parsed = _parse_profile_json(raw)
        if not parsed:
            return
        session.user_profile = json.dumps(parsed, ensure_ascii=False)
        db.commit()
        db.refresh(session)
    except (APIConnectionError, APITimeoutError, AuthenticationError, APIError, ValueError):
        return


def _thinking_extra_body() -> dict:
    if settings.deepseek_disable_thinking:
        return {"thinking": {"type": "disabled"}}
    return {}


def _stream_llm_tokens(
    messages: list[dict[str, str]], temperature: float, max_tokens: int
) -> Iterator[str]:
    client = _get_llm_client()
    extra_body = _thinking_extra_body()
    base_kwargs: dict = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if extra_body:
        base_kwargs["extra_body"] = extra_body

    for token_key in ("max_tokens", "max_completion_tokens"):
        kwargs = {**base_kwargs, token_key: max_tokens}
        try:
            stream = client.chat.completions.create(**kwargs)
            for chunk in stream:
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    yield text
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
    extra_body = _thinking_extra_body()
    base_kwargs: dict = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": temperature,
    }
    if extra_body:
        base_kwargs["extra_body"] = extra_body

    for token_key in ("max_tokens", "max_completion_tokens"):
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
        raw = _create_chat_completion(client, messages, temperature, max_tokens)
        return _ensure_reply_layers(
            raw,
            bullet_advice=is_generic_advice(session.position_label),
            limit_contingent_advice=is_contingent_advice(session.position_label),
        )
    except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
        raise ValueError(_llm_error_message(exc)) from exc


def _mock_ai_reply(session: UserSession) -> str:
    round_no = session.ai_round_count + 1
    if is_ingroup(session.emotion_label):
        return f"这确实太不公平了！（第{round_no}轮模拟回复，请配置 DEEPSEEK_API_KEY 以启用真实对话。）"
    return f"我理解你的感受，我们可以慢慢聊聊。（第{round_no}轮模拟回复，请配置 DEEPSEEK_API_KEY 以启用真实对话。）"


def _ensure_reply_layers(
    text: str,
    *,
    bullet_advice: bool = False,
    limit_contingent_advice: bool = False,
) -> str:
    """兜底：末尾有单个追问；尽量保留三段空行分隔；保留正文内换行。"""
    content = (text or "").strip()
    if not content:
        return content

    has_question = "？" in content or "?" in content
    if not has_question:
        content = f"{content}\n\n你最希望先改善哪一个沟通点？"
    formatted = _format_reply_paragraphs(content)
    if bullet_advice:
        formatted = _ensure_advice_bullets(formatted)
    if limit_contingent_advice:
        formatted = _enforce_contingent_advice_length(formatted)
    return formatted


def _enforce_contingent_advice_length(content: str) -> str:
    """将 contingent 第二段合并为单段，并硬限制在配置的最大字数内。"""
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(parts) < 3:
        return text

    stance = parts[0]
    question = _collapse_to_one_line(parts[-1])
    advice = _collapse_to_one_line(" ".join(parts[1:-1]))
    if len(advice) > ADVICE_MAX_CHARS:
        candidate = advice[:ADVICE_MAX_CHARS]
        sentence_end = max(candidate.rfind(mark) for mark in "。！？；")
        if sentence_end + 1 >= ADVICE_MIN_CHARS:
            advice = candidate[: sentence_end + 1]
        else:
            advice = f"{candidate[: ADVICE_MAX_CHARS - 1].rstrip('，、；：')}。"

    return f"{stance}\n\n{advice}\n\n{question}"


def _ensure_advice_bullets(content: str) -> str:
    """Generic 建议段：强制统一为「- **小标题**：内容」。"""
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    parts = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    # 至少：立场 + 建议 + 追问
    if len(parts) < 3:
        return text

    stance = parts[0].strip()
    question = parts[-1].strip()
    advice_raw = "\n".join(parts[1:-1])
    normalized: list[str] = []
    for line in advice_raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[-•*]\s+", "", stripped)
        stripped = re.sub(r"^\d+[\.、)\]］]\s*", "", stripped)
        title_match = re.match(
            r"^(?:\*\*)?([^：:\n*]{1,12})(?:\*\*)?\s*[：:]\s*(.+)$",
            stripped,
        )
        if title_match:
            title, body = title_match.groups()
            stripped = f"**{title.strip()}**：{body.strip()}"
        normalized.append(f"- {stripped}")

    if not normalized:
        return text
    return f"{stance}\n\n" + "\n".join(normalized) + f"\n\n{question}"


def _collapse_to_one_line(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _paragraph_has_question(text: str) -> bool:
    return "？" in text or "?" in text


def _format_reply_paragraphs(content: str) -> str:
    """整理为：立场回应 / 建议 / 追问（段间空一行）；追问强制合并为单行。"""
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)

    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not parts:
        return text

    # 从末尾取出连续含问号的段落，全部并入第三段追问
    split_at = len(parts)
    while split_at > 0 and _paragraph_has_question(parts[split_at - 1]):
        split_at -= 1
    # 至少保留一段正文，避免整段都被当成追问
    if split_at == 0 and len(parts) > 1:
        split_at = 1
    elif split_at == 0:
        split_at = 0

    if split_at < len(parts):
        body_parts = parts[:split_at]
        question = _collapse_to_one_line(" ".join(parts[split_at:]))
    else:
        # 没有独立追问段：用最后一个问句截取，并压成单行
        question_mark_idx = max(text.rfind("？"), text.rfind("?"))
        if question_mark_idx == -1:
            return text
        question_start = question_mark_idx
        while question_start > 0 and text[question_start - 1] not in "。！？\n":
            question_start -= 1
        while question_start < question_mark_idx and text[question_start] in " \t":
            question_start += 1
        body = text[:question_start].rstrip()
        question = _collapse_to_one_line(text[question_start : question_mark_idx + 1])
        body_parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if not body_parts:
            body_parts = ["我理解你现在的处境，这件事确实会让人感到压力。"]

    if not question:
        question = "你最希望先改善哪一个沟通点？"

    if not body_parts:
        body_parts = ["我理解你现在的处境，这件事确实会让人感到压力。"]

    if len(body_parts) >= 2:
        stance = body_parts[0]
        advice = "\n\n".join(body_parts[1:])
        return f"{stance}\n\n{advice}\n\n{question}"

    body = body_parts[0]
    # 单段正文：尝试按建议线索切开
    advice_markers = ("建议你", "你可以", "不妨", "可以先", "**", "1.", "①", "- ")
    cut = -1
    for marker in advice_markers:
        idx = body.find(marker)
        if idx > 0 and (cut == -1 or idx < cut):
            cut = idx
    if cut > 0:
        return f"{body[:cut].rstrip()}\n\n{body[cut:].lstrip()}\n\n{question}"
    return f"{body}\n\n{question}"


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
        condition = session_condition(session)
        user_msg = save_user_message(db, session, message)
        yield ": stream-open\n\n"
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

        if is_contingent_advice(session.position_label):
            # 先生成本轮语义摘要，等待提示与随后回复共享同一份最新画像。
            _refresh_user_profile(db, session)
            yield _sse_event(
                "memory",
                {"label": memory_cue_from_profile(session.user_profile)},
            )

        yield _sse_event("thinking", {})
        parts: list[str] = []
        for token in stream_ai_reply_tokens(db, session):
            parts.append(token)
            yield _sse_event("token", {"delta": token})

        full_content = _ensure_reply_layers(
            "".join(parts).strip(),
            bullet_advice=is_generic_advice(session.position_label),
            limit_contingent_advice=is_contingent_advice(session.position_label),
        )
        if is_contingent_advice(session.position_label):
            full_content = _replace_verbatim_user_quotes(
                full_content,
                user_msg.content,
                memory_cue_from_profile(session.user_profile),
            )
            full_content = _dedupe_paraphrase_leads(full_content)
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
