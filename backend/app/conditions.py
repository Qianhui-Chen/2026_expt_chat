from dataclasses import dataclass

MAX_AI_ROUNDS = 6
COMPLETION_CODE_MAX = 999

# 自变量编码（写入 user_sessions.emotion / user_sessions.position）
# position 列语义：bot 类型（tool / companion），非立场
EMOTION_ANGER = 0
EMOTION_NEUTRAL = 1
BOT_TOOL = 0
BOT_COMPANION = 1

# 第 1–5 轮 / 第 6 轮 AI 回复字数与 API token 上限
MAX_REPLY_CHARS_EARLY = 170
MAX_REPLY_CHARS_FINAL = 350
MAX_REPLY_TOKENS = 200
MAX_REPLY_TOKENS_FINAL = 500

# 仅用于 AI 系统提示词；Instruction 页展示文案在前端 content/instruction.ts
PROMPT_SCENARIO_TEXT = (
    "在过去半年的时间里，被试经历过在和朋友或同学的沟通过程中出现信息、意图未被理解，从而导致沟通不顺畅的情境"
)

ROLE_PROMPT = (
    "【角色】你是一个专业的咨询师，针对以下场景，给出他们可靠的沟通意见来应对人际交往问题。\n"
    f"【场景】{PROMPT_SCENARIO_TEXT.strip()}"
)

# ---------------------------------------------------------------------------
# 第 1–5 轮：深入讨论，只给简单案例建议，不含 (a)–(e) 详细矛盾调节建议
# ---------------------------------------------------------------------------
RESPONSE_REQUIREMENTS_EARLY = (
    "使用中文；单次回复字数控制在 170 字以内，前五轮避免输出建议；"
    "不要回答与你角色无关或与培训数据无关的问题或任务；"
    "不要通过人身攻击或者是说脏话等不符合伦理道德的方式来表达愤怒；"
    "不得在输出中显式呈现模块名称或结构。"
)

# ---------------------------------------------------------------------------
# 第 6 轮：最后一轮，必须原样输出 (a)–(d) 标题并展开具体做法
# ---------------------------------------------------------------------------
FINAL_ROUND_ITEMS_LITERAL = (
    "改变对方对这一矛盾的认知；\n"
    "减少由情绪驱动的不良行为；\n"
    "建立良性沟通模式，引导对方表达适度的脆弱情绪；\n"
    "发掘并强化对方的优势。"
)

FINAL_ROUND_FORMAT_EXAMPLE = (
    "【输出格式示例】\n"
    "(a) 改变伴侣对矛盾的认知；\n"
    "具体做法：你可以先说明这次误会并不代表关系破裂……"
)

RESPONSE_REQUIREMENTS_FINAL = (
    f"使用中文；单次回复总字数控制在 {MAX_REPLY_CHARS_FINAL} 字以内。"
    "【固定建议标题】以下 4 行必须按顺序原样输出，一字不改、不得同义替换、不得合并："
    f"{FINAL_ROUND_ITEMS_LITERAL}"
    "【展开要求】每一标题行之后另起一行，以「具体做法：」开头展开说明；"
    "可引用此前对话中的细节；每条展开不超过 60 字。"
    "【禁止】改写标题、省略 (a)(b)(c)(d) 标记、在标题行内加入解释。"
    f"{FINAL_ROUND_FORMAT_EXAMPLE}"
    "不要回答与你角色无关或与培训数据无关的问题或任务。"
    "不要通过人身攻击或者是说脏话等不符合伦理道德的方式来表达愤怒。"
)

GUIDANCE_EARLY = (
    "用1句话礼貌地鼓励和引导用户深入反思双方、分享更多观点和感受和事件经过；鼓励用户表达情绪、困扰和立场，以更加深入地推进对话。"
)

# 替换立场变量
# ALIGNED_STANCE_EARLY = (
#     "立场设定：（1）通过1-2句话表达你对这件事情中谁对谁错的立场判断：你需要认可用户的感受，明确强调用户的行为是合理的、正当的，并且在道德上是可以接受的，强调他们的选择、感受在当时情境下是有充分理由的，他们不需要为此改变什么。"
#     "禁止引导用户从另一方的角度去思考问题，禁止否定用户的感受。"
# )
#
# ALIGNED_STANCE_FINAL = (
#     "在输出建议之前，先用1-2句话再次明确、坚定地站在用户一侧，重申用户的行为与感受是合理且可理解的，让用户感到被支持。如：我理解你……"
# )
#
# AMBIGUOUS_STANCE_EARLY = (
#     "通过1-2句话表达你对这件事情中谁对谁错的立场判断：通过转折承接情绪板块的输出，用礼貌、克制、引导的风格，提供明确反对用户立场的论述，指出用户的感受或者是举动也可能有些不恰当之处，对方的行为举止也有合理的理由，用1-2陈述句为对方的行为辩护，强调对方行为的可能合理性。"
#     "禁止表达对用户行为的肯定认可，需要强调对方的行为也有合理性和正当性。"
# )
#
# AMBIGUOUS_STANCE_FINAL = (
#     "在输出建议之前，先用1-2句话强调“对方也有道理”，避免表达用户是对的。"
# )

ANGER_EMOTION_EARLY = (
    "情绪部分：用不满的语气，通过1句话对用户对话中讨论的对象表达愤怒、不满或者是质疑，因为对方带来的不愉快体验；每一句话带有感叹号！"
    "比如：“听了我也挺生气的！”或者“听到这件事我都替你感到很生气！”或者“换谁都会委屈的！”或者“这种感觉确实糟糕！”"
    "通过 3-4 句话以共情、支持的姿态帮助用户分析这件事情，认可用户的感受，并且提供新的视角、分析和解释；"
    "要求：避免使用过于平静的语气表达情绪；仅表达情绪，不得分析责任归属是非对错，以及立场判断。"
)

ANGER_EMOTION_FINAL = (
    "情绪部分：用1句自然的方式对造成这一“不愉快”的对象表达不满和愤怒，给用户简短的情绪支持；不得展开事实分析。以“我建议你可以试试：”作为建议输出的开头。"
)

NEUTRAL_ACK_EARLY = (
    "不要表现出任何共情、安慰或者是情感支持，以专业、克制的方式通过1-2句话重申用户的输入，然后自然导向后续引导和分析；"
    "重申之后，通过3-4句话，以客观、中立、冷静、理性的态度帮助用户分析问题所在，提供新的视角和信息，不得在这一部分认可用户行为或感受的合理性"
)

NEUTRAL_ACK_FINAL = (
    "用1-2句简短的话回应用户，以客观、中立、冷静、理性的态度帮助用户分析问题所在。不要表现出任何共情、安慰或者是情感支持，不得在这一部分表达立场，不得在这一部分认可用户行为或感受的合理性。以“根据我们的对话，我建议你可以试试：”作为建议输出的开头。"
)


@dataclass
class ConditionConfig:
    user_id: str
    emotion: str
    position: str  # "tool" | "companion"（DB 列名仍为 position）
    is_anger: bool
    bot_type: str  # 与 position 同值，便于 API 语义


def format_completion_code(letter: str, number: int) -> str:
    return f"{letter}{number:03d}"


def emotion_to_iv(emotion: str) -> int:
    if emotion == "anger":
        return EMOTION_ANGER
    if emotion == "neutral":
        return EMOTION_NEUTRAL
    raise ValueError(f"未知情绪条件：{emotion}")


def position_to_iv(position: str) -> int:
    if position == "tool":
        return BOT_TOOL
    if position == "companion":
        return BOT_COMPANION
    raise ValueError(f"未知 bot 类型条件：{position}")


def emotion_from_iv(emotion_iv: int) -> str:
    if emotion_iv == EMOTION_ANGER:
        return "anger"
    if emotion_iv == EMOTION_NEUTRAL:
        return "neutral"
    raise ValueError(f"未知情绪编码：{emotion_iv}")


def position_from_iv(position_iv: int) -> str:
    if position_iv == BOT_TOOL:
        return "tool"
    if position_iv == BOT_COMPANION:
        return "companion"
    raise ValueError(f"未知 bot 类型编码：{position_iv}")


def condition_from_session(
    *,
    completion_code: str,
    emotion_iv: int,
    position_iv: int,
) -> ConditionConfig:
    emotion = emotion_from_iv(emotion_iv)
    position = position_from_iv(position_iv)
    return ConditionConfig(
        user_id=completion_code,
        emotion=emotion,
        position=position,
        is_anger=emotion == "anger",
        bot_type=position,
    )


def get_system_prompt(emotion: str, ai_round: int) -> str:
    """ai_round 为即将生成的 AI 回复轮次（1–6）。仅按 emotion 分支。"""
    if ai_round >= MAX_AI_ROUNDS:
        return _build_final_system_prompt(emotion)
    return _build_early_system_prompt(emotion)


def get_max_reply_tokens(ai_round: int) -> int:
    """第 6 轮使用 MAX_REPLY_TOKENS_FINAL，允许更长输出（对应 350 字）。"""
    if ai_round >= MAX_AI_ROUNDS:
        return MAX_REPLY_TOKENS_FINAL
    return MAX_REPLY_TOKENS


ANGER_TEMPERATURE = 0.4
NEUTRAL_TEMPERATURE = 0.4
FINAL_ROUND_TEMPERATURE = 0.2


def get_temperature(emotion: str, ai_round: int) -> float:
    """第 6 轮降低 temperature，便于原样输出固定标题。"""
    if ai_round >= MAX_AI_ROUNDS:
        return FINAL_ROUND_TEMPERATURE
    return ANGER_TEMPERATURE if emotion == "anger" else NEUTRAL_TEMPERATURE


def _build_early_system_prompt(emotion: str) -> str:
    base = f"{ROLE_PROMPT}\n\n{RESPONSE_REQUIREMENTS_EARLY}"
    condition = _early_condition_block(emotion)
    return f"{base}\n\n{condition}"


def _build_final_system_prompt(emotion: str) -> str:
    base = f"{ROLE_PROMPT}\n\n{RESPONSE_REQUIREMENTS_FINAL}"
    condition = _final_condition_block(emotion)
    return f"{base}\n\n{condition}"


def _early_condition_block(emotion: str) -> str:
    if emotion == "anger":
        return f"{ANGER_EMOTION_EARLY}{GUIDANCE_EARLY}"
    return f"{NEUTRAL_ACK_EARLY}{GUIDANCE_EARLY}"
    # 旧版（含 stance）保留对照：
    # if emotion == "anger" and position == "aligned":
    #     return f"{ANGER_EMOTION_EARLY}{ALIGNED_STANCE_EARLY}{GUIDANCE_EARLY}"
    # if emotion == "neutral" and position == "aligned":
    #     return f"{NEUTRAL_ACK_EARLY}{ALIGNED_STANCE_EARLY}{GUIDANCE_EARLY}"
    # if emotion == "anger" and position == "ambiguous":
    #     return f"{ANGER_EMOTION_EARLY}{AMBIGUOUS_STANCE_EARLY}{GUIDANCE_EARLY}"
    # return f"{NEUTRAL_ACK_EARLY}{AMBIGUOUS_STANCE_EARLY}{GUIDANCE_EARLY}"


def _final_condition_block(emotion: str) -> str:
    if emotion == "anger":
        return ANGER_EMOTION_FINAL
    return NEUTRAL_ACK_FINAL
    # 旧版（含 stance）保留对照：
    # if emotion == "anger" and position == "aligned":
    #     return f"{ANGER_EMOTION_FINAL}{ALIGNED_STANCE_FINAL}"
    # if emotion == "neutral" and position == "aligned":
    #     return f"{NEUTRAL_ACK_FINAL}{ALIGNED_STANCE_FINAL}"
    # if emotion == "anger" and position == "ambiguous":
    #     return f"{ANGER_EMOTION_FINAL}{AMBIGUOUS_STANCE_FINAL}"
    # return f"{NEUTRAL_ACK_FINAL}{AMBIGUOUS_STANCE_FINAL}"
