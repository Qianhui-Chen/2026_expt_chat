export const MAX_ANGER_METER = 10;

/** 每一轮 AI 回复（第 1–9 轮）各给一个 6–8 的稳定随机值（同一会话内不变） */
export function getAngerMeterLevel(
  roundNumber: number | null | undefined,
  sessionToken: number
): number {
  if (!roundNumber || roundNumber <= 0 || !sessionToken) {
    return 0;
  }
  const seed = sessionToken * 31 + roundNumber * 17;
  return 6 + (Math.abs(seed) % 3);
}

export function getPendingAngerMeterLevel(nextRound: number, sessionToken: number): number {
  return getAngerMeterLevel(nextRound, sessionToken);
}
