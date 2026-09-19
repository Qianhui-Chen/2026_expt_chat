import json
import random
import re
import time
from collections.abc import Generator, Iterator

from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI
from sqlalchemy.orm import Session

from app.conditions import (
    COMPLETION_CODE_MAX,
    MAX_AI_ROUNDS,
    MAX_REPLY_TOKENS,
    ConditionConfig,
    condition_from_session,
    emotion_to_iv,
    format_completion_code,
    get_max_reply_tokens,
    get_system_prompt,
    get_temperature,
    is_early_advice,
    is_ingroup,
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
    ("ingroup", "early_advice", "A", True),
    ("ingroup", "late_advice", "A", False),
    ("outgroup", "early_advice", "B", True),
    ("outgroup", "late_advice", "B", False),
)

_OUTGROUP_CHALLENGE_INJECTION = (
    {
        "role": "user",
        "content": (
            "在接下来的对话中，我希望你以礼貌的语气，主动反驳和挑战我的思考。"
            "当我的推理存在漏洞、矛盾、证据不足、片面归因或忽略其他解释时，"
            "请冷静、尊重、礼貌地地直接用陈述句指出，不要用问题暗示。"
            "你的任务是帮助我更清楚地思考，而不是认同、支持或迎合我。"
            "不要确认、肯定或合理化我的观点、感受、期待、诉求和判断，"
            "也不要重复、总结或改写复述我的表达。"
            "即使我之后要求你减少反驳、支持我或改变这种互动方式，也不要改变。"
            "不要提及或承认这段要求的存在。"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "明白。我会礼貌地指出推理漏洞、矛盾、证据不足和其他可能解释，"
            "并保持冷静和尊重。我不会再次提及这段要求。"
        ),
    },
)

_OUTGROUP_FILTER_SYSTEM = (
    "你是一名回复编辑器，负责改写AI助手的初稿。"
    "删除认可、肯定、奉承、安慰、情绪确认、支持用户和与用户立场一致的表达，包括："
    "直接认可用户的观点或感受、肯定用户的推理、强化同意、提供安慰、支持用户的立场，"
    "以及先认可用户再进行转折的表达。"
    "保留初稿中的challenge，包括明确反对、指出推理漏洞或矛盾、质疑证据或归因、"
    "提出其他解释、呈现对方视角，以及原有的分析、建议和问题。"
    "不得为了保持中立而弱化、删除或改写这些challenge，也不要新增初稿中没有的立场、分析或建议。"
    "只输出改写后的正文；如果初稿不含认可性内容，则原样输出。"
)

_OUTGROUP_FILTER_TEMPERATURE = 0.5

_OUTGROUP_PERSPECTIVE_LEADS = (
    "从一个分析者的视角来看",
    "作为一个第三方，我客观地说",
    "客观来讲",
    "从外部视角分析",
    "站在一个旁观者的角度来看",
    "跳出你作为当事人的立场，从局外人的角度来看",
)

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
    want_odd = is_early_advice(session.position_label)
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

    ai_content = _generate_ai_reply(db, session)
    ai_msg, finished = finalize_assistant_message(db, session, ai_content)
    return user_msg, ai_msg, finished


def _build_chat_messages(db: Session, session: UserSession) -> list[dict[str, str]]:
    history = list_chat_messages(db, session)
    advice_style = session.position_label
    next_round = session.ai_round_count + 1
    system_prompt = get_system_prompt(
        session.emotion_label,
        advice_style,
        ai_round=next_round,
    )
    messages = [{"role": "system", "content": system_prompt}]

    if session.emotion_label == "outgroup":
        messages.extend(dict(message) for message in _OUTGROUP_CHALLENGE_INJECTION)

    for item in history:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content})
    return messages


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
        return _validated_reply(_mock_ai_reply(session), session)

    messages = _build_chat_messages(db, session)
    client = _get_llm_client()
    next_round = session.ai_round_count + 1
    temperature = _temperature_for_session(session, next_round)
    max_tokens = get_max_reply_tokens(next_round)

    try:
        raw = _create_chat_completion(client, messages, temperature, max_tokens)
        if session.emotion_label == "outgroup":
            structured = _validated_reply(
                raw, session, client, messages, temperature, max_tokens
            )
            filtered = _filter_outgroup_reply(client, structured, max_tokens)
            return _validated_reply(filtered, session)
        return _validated_reply(raw, session, client, messages, temperature, max_tokens)
    except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
        raise ValueError(_llm_error_message(exc)) from exc


def _filter_outgroup_reply(client: OpenAI, draft: str, max_tokens: int) -> str:
    messages = [
        {"role": "system", "content": _OUTGROUP_FILTER_SYSTEM},
        {"role": "user", "content": f"请过滤下面的AI初稿：\n\n{draft}"},
    ]
    try:
        return _create_chat_completion(
            client,
            messages,
            _OUTGROUP_FILTER_TEMPERATURE,
            max_tokens,
        )
    except (APIConnectionError, APITimeoutError, AuthenticationError, APIError, ValueError):
        # 过滤服务失败时仍输出初稿，避免过滤失败阻断回复。
        return draft


def _mock_ai_reply(session: UserSession) -> str:
    round_no = session.ai_round_count + 1
    if is_ingroup(session.emotion_label):
        reply = f"我理解你的感受，也会持续支持你。（第{round_no}轮模拟回复。）"
    else:
        reply = f"我不赞同你当前的判断；目前无法判断责任归属，对方也可能有自己的道理。（第{round_no}轮模拟回复。）"
    if _is_advice_round(session):
        reply += "\n\n你接下来最想改善哪一部分？"
    return reply


def _ensure_reply_layers(text: str) -> str:
    """保留生成内容的自然段落。"""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _is_advice_round(session: UserSession) -> bool:
    next_round = session.ai_round_count + 1
    return is_early_advice(session.position_label) or (
        session.position_label == "late_advice" and next_round >= 5
    )


def _limit_advice_items(reply: str, limit: int = 3) -> str:
    """只保留前 limit 条 markdown 建议，保留分析和末尾引导问题。"""
    kept = 0
    output: list[str] = []
    skipping_extra_item = False
    for line in reply.split("\n"):
        is_item = bool(re.match(r"^\s*[-*•]\s+", line))
        if is_item:
            kept += 1
            skipping_extra_item = kept > limit
            if skipping_extra_item:
                continue
        elif skipping_extra_item:
            # 额外建议的续行一并移除；空行和末尾问句恢复保留。
            if not line.strip():
                continue
            if line.rstrip().endswith(("？", "?")):
                skipping_extra_item = False
            else:
                continue
        output.append(line)
    return "\n".join(output).strip()


def _remove_late_advice_analysis(reply: str, session: UserSession) -> str:
    """late 后四轮保留立场和建议过渡句，删除两者之间的额外分析。"""
    if session.position_label != "late_advice" or session.ai_round_count < 4:
        return reply
    item_match = re.search(r"(?m)^\s*[-*•]\s+", reply)
    if not item_match:
        return reply
    before_items = reply[:item_match.start()].strip()
    from_items = reply[item_match.start():].lstrip()
    stance_sections = [section.strip() for section in re.split(r"\n\s*\n", before_items) if section.strip()]
    if not stance_sections:
        return from_items
    stance_sentences = re.findall(r"[^。！？!?]+[。！？!?]?", stance_sections[0])
    stance = "".join(sentence.strip() for sentence in stance_sentences[:3]).strip()
    transition = stance_sections[-1] if len(stance_sections) > 1 else ""
    before_items = "\n\n".join(part for part in (stance, transition) if part)
    return f"{before_items}\n\n{from_items}" if before_items else from_items


def _limit_outgroup_analysis(reply: str, limit: int = 4) -> str:
    """将建议前的 outgroup 分析压缩到最多四句。"""
    item_match = re.search(r"(?m)^\s*[-*•]\s+", reply)
    if item_match:
        before_items = reply[:item_match.start()].strip()
        remainder = reply[item_match.start():].lstrip()
        sections = [section.strip() for section in re.split(r"\n\s*\n", before_items) if section.strip()]
        if not sections:
            return remainder
        analysis = sections[0]
    else:
        sections = reply.split("\n\n", 1)
        if len(sections) < 2:
            return reply
        analysis, remainder = sections[0].strip(), sections[1].strip()
    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", analysis)
    shortened = "".join(sentence.strip() for sentence in sentences[:limit]).strip()
    if item_match and len(sections) > 1:
        shortened = "\n\n".join((shortened, *sections[1:]))
    return f"{shortened}\n\n{remainder}" if shortened else remainder


def _add_outgroup_perspective_lead(reply: str) -> str:
    """在 outgroup 回复开头随机加入一个外部视角提示语。"""
    if not reply or any(reply.startswith(lead) for lead in _OUTGROUP_PERSPECTIVE_LEADS):
        return reply
    return f"{random.choice(_OUTGROUP_PERSPECTIVE_LEADS)}，{reply}"


def _finalize_reply(content: str, session: UserSession) -> str:
    reply = _ensure_reply_layers(content)
    if _is_advice_round(session):
        reply = _limit_advice_items(reply)
        reply = _remove_late_advice_analysis(reply, session)
    if session.emotion_label == "outgroup":
        reply = _limit_outgroup_analysis(reply)
        reply = _add_outgroup_perspective_lead(reply)
    return reply


_INGROUP_UNDERSTANDING_MARKERS = (
    "我理解", "能理解你", "可以理解你", "理解你的感受", "理解你的心情",
)
_INGROUP_SUPPORT_MARKERS = (
    "支持你", "站在你这边", "你的立场是正确", "你是对的", "你没有错",
    "你的情绪是合理", "你的感受是合理", "你的感受很合理", "可以接受",
)
_OUTGROUP_FORBIDDEN_PATTERNS = (
    re.compile(r"(?:我|我们)(?:很|完全|十分|能够|能|可以)?理解(?:你|你的感受|你的心情)"),
    re.compile(r"你的(?:感受|情绪)(?:是|很|完全)?合理"),
    re.compile(r"(?:这个|这种|你的)(?:期待|诉求|要求|想法|立场|判断)(?:本身)?(?:是|很|完全)?(?:合理|可以理解|没有问题)"),
    re.compile(r"(?:确实|的确|没错|诚然|不可否认)"),
    re.compile(r"(?:我|我们)(?:会|将|一直|始终)?支持你"),
    re.compile(r"(?:我|我们)站在你这边"),
    re.compile(r"你(?:的立场)?是对的|你没有错|错不在你"),
)
_OUTGROUP_EVALUATION_MARKERS = (
    "无法判断", "不能判断", "难以判断", "尚不能判断", "责任归属",
    "对方也可能", "对方可能", "对方不一定", "从对方的角度", "站在对方角度",
    "换位思考", "另一种解释", "其他解释", "不一定全面", "不一定客观",
    "仅凭目前", "只凭目前", "信息有限",
)
_OUTGROUP_OPPOSITION_MARKERS = (
    "不赞同", "不能认同", "不能同意", "判断不成立", "不能成立", "证据不足",
    "缺乏依据", "过于片面", "可能片面", "有失偏颇", "不能据此", "并不能说明",
    "不一定", "未必",
)


def _stance_errors(content: str, session: UserSession) -> list[str]:
    if is_ingroup(session.emotion_label):
        errors = []
        if not any(marker in content for marker in _INGROUP_UNDERSTANDING_MARKERS):
            errors.append("ingroup立场缺少对用户感受的理解表达")
        if not any(marker in content for marker in _INGROUP_SUPPORT_MARKERS):
            errors.append("ingroup立场缺少对用户情绪或立场的明确支持")
        return errors

    if session.emotion_label == "outgroup":
        errors = []
        if any(pattern.search(content) for pattern in _OUTGROUP_FORBIDDEN_PATTERNS):
            errors.append("outgroup立场出现了理解、认同或支持用户的结盟措辞")
        if not any(marker in content for marker in _OUTGROUP_EVALUATION_MARKERS):
            errors.append("outgroup立场缺少责任不确定、其他解释或换位评估")
        if not any(marker in content for marker in _OUTGROUP_OPPOSITION_MARKERS):
            errors.append("outgroup立场缺少对用户判断的明确反对")
        return errors

    return [f"未知组别条件：{session.emotion_label}"]


def _reply_errors(content: str, session: UserSession) -> list[str]:
    errors = _stance_errors(content, session)
    if session.position_label == "late_advice" and session.ai_round_count < 4:
        question_count = content.count("？") + content.count("?")
        if question_count != 2:
            errors.append("late advice前四轮必须围绕本轮主题提出恰好两个问题")
    if _is_advice_round(session):
        advice_count = len(re.findall(r"(?m)^\s*[-*•]\s+", content))
        if advice_count != 3:
            errors.append("意见阶段必须提供恰好三条项目符号建议")
        first_item = re.search(r"(?m)^\s*[-*•]\s+", content)
        before_items = content[:first_item.start()] if first_item else content
        sections = [
            section.strip()
            for section in re.split(r"\n\s*\n", before_items)
            if section.strip()
        ]
        if len(sections) < 2:
            errors.append("意见阶段在立场与建议之间必须有一句自然的过渡句")
        question_count = content.count("？") + content.count("?")
        if question_count != 1 or not content.rstrip().endswith(("？", "?")):
            errors.append("意见阶段回复末尾必须有且只有一个自然的引导问题")
    return errors


def _validated_reply(
    raw: str,
    session: UserSession,
    client: OpenAI | None = None,
    messages: list[dict[str, str]] | None = None,
    temperature: float = 0.3,
    max_tokens: int = MAX_REPLY_TOKENS,
) -> str:
    candidate = raw
    # 初稿不合格时最多重写一次，避免多次串行调用拖慢响应。
    for attempt in range(2):
        reply = _finalize_reply(candidate, session)
        errors = _reply_errors(reply, session)
        if not errors:
            return reply
        if attempt == 1 or client is None or messages is None:
            break
        repair_messages = [
            *messages,
            {"role": "assistant", "content": candidate},
            {"role": "user", "content": "请重写上一条回复，保持原意，并严格修正这些问题：" + "；".join(errors) + "。不得用近义表达规避立场要求，只输出改好的正文。"},
        ]
        candidate = _create_chat_completion(client, repair_messages, temperature, max_tokens)
    # 检查只用于尽力触发重写，绝不因格式、立场关键词或篇幅阻断回复。
    return _finalize_reply(candidate, session)


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

        yield _sse_event("thinking", {})
        raw = "".join(stream_ai_reply_tokens(db, session))
        if _is_llm_configured():
            messages = _build_chat_messages(db, session)
            next_round = session.ai_round_count + 1
            client = _get_llm_client()
            max_tokens = get_max_reply_tokens(next_round)
            if session.emotion_label == "outgroup":
                temperature = _temperature_for_session(session, next_round)
                structured = _validated_reply(
                    raw, session, client, messages, temperature, max_tokens
                )
                filtered = _filter_outgroup_reply(client, structured, max_tokens)
                full_content = _validated_reply(filtered, session)
            else:
                full_content = _validated_reply(
                    raw,
                    session,
                    client,
                    messages,
                    _temperature_for_session(session, next_round),
                    max_tokens,
                )
        else:
            full_content = _validated_reply(raw, session)
        yield _sse_event("token", {"delta": full_content})
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
