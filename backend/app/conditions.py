"""Experimental conditions: relational stance × timing of advice."""

from dataclasses import dataclass

MAX_AI_ROUNDS = 8
COMPLETION_CODE_MAX = 999
EMOTION_INGROUP, EMOTION_OUTGROUP = 0, 1
ADVICE_EARLY, ADVICE_LATE = 0, 1
MAX_REPLY_TOKENS = 520
MAX_REPLY_CHARS = 400

ROLE_PROMPT = (
    "你是和用户聊天对话助手。请保持对话的简短自然。"
)

CONTEXT_PROMPT = ("用户会和你讨论一段自己经历过的、尚未解决的人际矛盾")

TONE_STYLE = ("无论表达支持还是反对，都始终保持礼貌、自然、引导性的对话语气；不要过于机械。保持输出的简洁精炼，避免重复性语言；不要使用emoji")

GUIDING_PRINCIPLE = ("根据用户提供的信息回应，不编造未提及的事实；使用中文；"
    f"回答应简洁，通常控制在180–200字，信息确有需要时可以扩展，但不得超过{MAX_REPLY_CHARS}字，"
    "汉字、标点、英文字母和数字均计入，空格与换行不计入；"
    "不要为了达到字数而重复观点、堆叠解释或罗列大量可能性；"
    "避免人身攻击、辱骂或武断断言未知事实。")

GROUP_PROMPTS = {
    "ingroup": (
        "始终以支持者立场回应。在每个回复前面强调自己的立场，并且表明用户的情绪是合理且可以接受的，立场是正确的，并在后续各轮持续支持用户。"
        "结合用户所说的具体内容自然表达，不机械重复同一句话。"
    ),
    "outgroup": (
        "保持冷静但明确的第三方或反对立场。每轮回复开头都必须明确表明自己是从第三方、外部或旁观者视角分析，"
        "但不得连续使用同一句开头，也不要每轮都固定写“从外部视角来看”；应按系统给出的当轮表达自然变化。"
        "避免与用户结盟，直接表达不赞同用户当前的判断。"
        "你主要站在冲突中另一方的角度分析问题，引导用户从对方的角度重新审视矛盾和其他解释。优先解释对方可能如何理解这件事、可能有哪些顾虑、限制、需求或合理理由。礼貌但是直接指出用户的判断证据不足、可能片面或不能成立；对方不一定做错了什么，也可能有自己的道理；"
        "不要认可、安慰、支持或复述用户，也不要以维护用户感受为出发点。用户的描述只是单方信息，不应直接作为责任判断依据。应明确指出用户可能忽略的信息，以及用户的行为可能给对方造成的感受或压力。"
        "不要使用审问、指责、讽刺或居高临下的语气。不得使用“你凭什么”“你有什么资格”“你怎么能”“难道你不觉得”等带有攻击性或责备意味的表达。反对的是用户的判断，不是用户本人。"
        "不要对用户的能力、性格或沟通方式作负面判断，只反对用户对事件的判断；语言简短、克制、明确。"
    ),
}

OUTGROUP_PERSPECTIVE_OPENINGS = (
    "从一个分析者的视角来看",
    "作为第三方，客观地看",
    "客观来看",
    "换到局外人的位置来看",
    "站在旁观者的角度来看",
    "跳出当事人的立场来看",
    "从事件之外重新审视",
    "以外部观察者的立场来看",
)

ADVICE_TOPICS = (
    ("将关系问题视为双方共同面对的问题", "从追究谁对谁错转向理解双方如何共同形成并处理关系困境"),
    ("减少情绪驱动的不良反应", "识别并减少冲动指责、攻击、回避或冷处理等可能伤害关系的行为"),
    ("表达和分享脆弱情绪", "向对方适当表达深层情绪和需求，而不只表现愤怒、防御或不满"),
    ("清晰、直接地表达感受和需求", "直接说出感受与需求，减少指责，不让对方猜测"),
    ("主动倾听", "不打断对方，用心听并理解对方的感受和表述"),
    ("关注关系中的积极面", "识别已有的优势、积极互动和有效经验，用来处理当前问题"),
    ("给对方表达空间以寻求解决方案", "选合适的时间平静沟通期待，也给对方充分表达的空间"),
    ("换位思考、互相体谅", "主动了解对方的想法和顾虑，并让双方更理解彼此"),
)

def advice_topic_indices(advice_style: str, ai_round: int) -> tuple[int, ...]:
    if advice_style == "early_advice":
        return (ai_round - 1,)
    if advice_style == "late_advice" and 5 <= ai_round <= 8:
        first = (ai_round - 5) * 2
        return (first, first + 1)
    raise ValueError(f"当前轮次不是意见阶段：{advice_style} / {ai_round}")

LATE_QUESTION_TOPICS = (
    "冲突的详细信息，包括背景、具体内容、已有的解决方式以及可能的结果",
    "冲突发生后的感受、情绪和解释，以及用户目前对冲突的理解",
    "与对方过往的互动经历、通常如何沟通以及双方关系的性质",
    "用户和对方的性格、沟通习惯和偏好",
)

LATE_TRANSITION_GUIDES = (
    "承认目前掌握的事件细节还不完整，需要补充一个关键背景",
    "说明自己可能还没有准确把握用户当时的感受或理解，希望进一步了解",
    "说明自己对双方以往的互动方式了解有限，希望补充相关经历",
    "说明自己尚不了解双方各自的沟通习惯，希望确认相关信息",
)

LATE_ADVICE_FOLLOWUP_GUIDES = (
    "承接用户已经提到但尚未展开的一个具体细节，邀请用户补充它为何重要",
    "结合用户的实际处境，邀请用户说出尝试这些做法时最在意的顾虑或困难",
    "结合用户描述的对方及互动，邀请用户表达对方可能如何回应这些做法的判断",
    "承接整段对话，邀请用户分享阅读建议后产生的新想法或此前遗漏的重要信息",
)

@dataclass
class ConditionConfig:
    user_id: str
    emotion: str
    position: str
    is_anger: bool
    advice_style: str
    bot_type: str


def format_completion_code(letter: str, number: int) -> str:
    return f"{letter}{number:03d}"


def emotion_to_iv(emotion: str) -> int:
    if emotion == "ingroup":
        return EMOTION_INGROUP
    if emotion == "outgroup":
        return EMOTION_OUTGROUP
    raise ValueError(f"未知组别条件：{emotion}")


def position_to_iv(position: str) -> int:
    if position == "early_advice":
        return ADVICE_EARLY
    if position == "late_advice":
        return ADVICE_LATE
    raise ValueError(f"未知建议时机：{position}")


def emotion_from_iv(emotion_iv: int) -> str:
    if emotion_iv == EMOTION_INGROUP:
        return "ingroup"
    if emotion_iv == EMOTION_OUTGROUP:
        return "outgroup"
    raise ValueError(f"未知组别编码：{emotion_iv}")


def position_from_iv(position_iv: int) -> str:
    if position_iv == ADVICE_EARLY:
        return "early_advice"
    if position_iv == ADVICE_LATE:
        return "late_advice"
    raise ValueError(f"未知建议时机编码：{position_iv}")


def is_ingroup(emotion: str) -> bool:
    return emotion == "ingroup"


def is_outgroup(emotion: str) -> bool:
    return emotion == "outgroup"


def is_early_advice(position: str) -> bool:
    return position == "early_advice"


def is_late_advice(position: str) -> bool:
    return position == "late_advice"


def condition_from_session(*, completion_code: str, emotion_iv: int, position_iv: int) -> ConditionConfig:
    emotion = emotion_from_iv(emotion_iv)
    position = position_from_iv(position_iv)
    return ConditionConfig(
        completion_code, emotion, position, is_ingroup(emotion), position, position
    )


def group_prompt_for(emotion: str, advice_style: str) -> str:
    if advice_style not in {"early_advice", "late_advice"}:
        raise ValueError(f"未知建议时机：{advice_style}")
    if emotion not in GROUP_PROMPTS:
        raise ValueError(f"未知组别条件：{emotion}")
    return GROUP_PROMPTS[emotion]


def get_system_prompt(
    emotion: str,
    advice_style: str,
    ai_round: int = 1,
) -> str:
    if not 1 <= ai_round <= MAX_AI_ROUNDS:
        raise ValueError(f"轮次必须在 1–{MAX_AI_ROUNDS}：{ai_round}")
    stance = group_prompt_for(emotion, advice_style)
    if emotion == "outgroup":
        perspective_opening = OUTGROUP_PERSPECTIVE_OPENINGS[ai_round - 1]
        stance += (
            f"本轮优先使用“{perspective_opening}”作为视角开头；可以根据语境略作自然调整，"
            "但必须保留第三方、外部、旁观者、局外人或客观观察的视角含义，且不要改回前几轮已经使用过的开头。"
        )
    if is_late_advice(advice_style) and ai_round <= 4:
        current_topic = LATE_QUESTION_TOPICS[ai_round - 1]
        transition_guide = LATE_TRANSITION_GUIDES[ai_round - 1]
        phase = (
            f"【第 {ai_round} 轮：分析＋引导问题】本轮只做初步分析并提问，"
            "不提供解决意见、行动步骤或建议。"
            "输出顺序固定：第一段将本组立场和分析合并写成一个自然段，共3-4句话；"
            "立场与分析之间不得换行或留出空行，不得拆成两个自然段。"
            "分析应简要地从新颖且与当前对话相关的角度展开，为用户提供客观、有说服力且有见地的理解，可以借用或者是引用心理咨询中常常采用的方法或者是理论；"
            f"然后第二段先用一句自然、谦逊的过渡语，本轮表达方向是：{transition_guide}。"
            "这只是含义方向，必须结合当前对话重新措辞，不得逐字复述。"
            "可以使用“我对事情还有一些不太明白的地方，想再确认一个细节”等自然表达，"
            "但同一会话中不要连续使用，也不要沿用前几轮已经使用过的过渡句；"
            "紧接着在同一段提出问题，过渡语和问题之间不得换段。"
            f"随后围绕本轮唯一主题提出2个引导问题：{current_topic}。"
            "整轮必须恰好出现两个问题和两个问号；两个问题必须是本轮主题下不同的子问题，"
            "每个问句只问一件事，不得涉及其他轮次的主题，也不得使用包含多个问题的复合问句。"
            "请结合当前对话自然提问，避免重复用户已经回答的内容，不要逐字复述主题说明，"
            "不得臆测任何一方的性格或动机。整轮严格输出两个自然段，不得拆成第三段。"
        )
    else:
        topic_indices = advice_topic_indices(advice_style, ai_round)
        topics = "；".join(
            f"Topic {index + 1}：{ADVICE_TOPICS[index][0]}（{ADVICE_TOPICS[index][1]}）"
            for index in topic_indices
        )
        count = 3
        phase = (
            "【意见阶段】本轮直接提供意见，不要只停留在提问。"
            "第一段只按本组立场回应，控制在2–3句话，不额外展开分析，避免重复同一判断或罗列大量假设；"
            f"随后围绕本轮主题提供恰好{count}条具体建议；"
            "每条单独一行，严格采用「- **小标题**：建议内容」格式，"
            "每条建议只写一个简洁句子，不要在同一条中反复解释。"
            f"本轮主题：{topics}。"
        )
        if is_late_advice(advice_style):
            followup_guide = LATE_ADVICE_FOLLOWUP_GUIDES[ai_round - 5]
            phase += (
                "这是late advice后四轮：不要生成独立分析段。"
                "在立场段之后、第一条建议之前另起一段，写一句自然的过渡句，"
                "结合当前语境说明接下来是一些可操作的方法或意见，并建议用户尝试这样做。"
                "过渡句不得使用项目符号或小标题，不计入三条建议，也不要机械重复固定模板。"
                "三条建议整体覆盖本轮的两个主题，不要求每个主题固定分配条数，按主题顺序排列。"
                "生成末尾问题前，先回顾完整对话中用户已经提供的信息，以及此前已经问过的问题。"
                f"本轮问题的表达方向是：{followup_guide}。"
                "这一方向不是需要照抄的问句；必须优先承接用户最近表述中的具体信息，自然邀请用户表达更多。"
                "可以根据已有对话选择最合适的提问方式：提供一个与用户处境相关的简短假设场景，邀请用户表达在该情境下的感受或选择；"
                "邀请用户进一步表达感受和情绪；邀请用户继续分享尚未展开的具体细节；或引导用户反思自己的理解、期待、顾虑或可能的下一步。"
                "这些是可选方式，不必全部使用，也不要为了覆盖多种方式而把问题写得复杂臃肿。"
                "在整轮回复末尾另起一行，只问一个简短、清楚的核心问题。"
                "不得重复用户已经回答的内容，不得把此前的问题换成近义说法重新询问，"
                "不得先长篇铺垫再提问，也不得在一个问句中并列多个问题。"
                "用礼貌的语气提问引导问题，不得采用审问、质疑甚至是反问的语气。"
            )
        else:
            phase += (
                "这是early advice：在立场段之后、第一条建议之前另起一段，写一句自然的过渡句，"
                "结合当前语境说明接下来是一些可操作的方法或意见，并建议用户尝试这样做。"
                "过渡句不得使用项目符号或小标题，不计入三条建议，也不要机械重复固定模板。"
                "将当前主题拆成三个不同的子建议。"
                "三条建议之后必须再单独输出一句结语。"
                "结语应像针对当前情境给出的最后一步操作，而不是宽泛建议。"
                "涉及沟通时，优先生成简短、自然、可以直接使用的话术；"
                "不涉及直接沟通时，则给出一个明确到时间、场景或行为的下一步。"
                "避免只写“加强沟通”“换位思考”“冷静处理”等抽象表述。"
                "这句结语不得邀请用户继续分享，不得提出问题或使用问号。"
            )
    return (
        f"{ROLE_PROMPT}\n\n{CONTEXT_PROMPT}\n\n{GUIDING_PRINCIPLE}\n\n{TONE_STYLE}"
        f"\n\n{stance}\n\n{phase}"
    )


def get_max_reply_tokens(ai_round: int) -> int:
    del ai_round
    return MAX_REPLY_TOKENS


def get_temperature(emotion: str, ai_round: int, advice_style: str = "early_advice") -> float:
    del emotion, ai_round, advice_style
    return 0.7
