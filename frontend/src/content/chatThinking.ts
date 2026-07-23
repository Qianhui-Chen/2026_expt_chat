/** 聊天等待态文案：每轮从池中抽 3 条，每 2 秒轮换；最短等待 6 秒 */

export const MIN_THINKING_MS = 6000;
export const THINKING_ROTATE_MS = 2000;
export const THINKING_PHRASE_COUNT = 3;
/** 揭示回复时的打字间隔（接近原 mock 流式节奏） */
export const TYPEWRITER_CHAR_DELAY_MS = 28;

export const TOOL_THINKING_PHRASES = [
  "思考中",
  "分析中",
  "计算中",
  "检索中",
  "深度思考",
  "输出中",
] as const;

export const COMPANION_THINKING_PHRASES = [
  "倾听中",
  "感受中",
  "摸摸你",
  "抱抱你",
  "拍拍……",
] as const;

function shuffleInPlace<T>(items: T[]): T[] {
  for (let i = items.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
  return items;
}

/** 每一轮对话从对应分组文案池中无放回抽取 3 条 */
export function pickThinkingPhrases(botType: "tool" | "companion"): string[] {
  const pool =
    botType === "companion" ? [...COMPANION_THINKING_PHRASES] : [...TOOL_THINKING_PHRASES];
  return shuffleInPlace(pool).slice(0, THINKING_PHRASE_COUNT);
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
