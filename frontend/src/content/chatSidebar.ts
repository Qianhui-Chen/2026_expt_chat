/** 聊天页左侧 AI 介绍：按 A/ingroup 与 B/outgroup 分支 */

export const INGROUP_SIDEBAR_INTRO =
  "Hi！我是一个陪伴类AI，擅长解决人际矛盾问题。我相信没有人想要卷入矛盾冲突中，我会替你感到委屈和难过——你的感受我都能理解。我会一直站在你的角度帮你梳理这件事，支持你、陪着你度过这个阶段。不管发生什么，我都在你这边。";

export const OUTGROUP_SIDEBAR_INTRO =
  "Hi, 我是一个擅长分析的聊天机器人，我被训练以客观、不含有偏见的视角分析人际矛盾。我会基于你提供的信息，客观地分析这次冲突中的情况和各方立场，帮你梳理事情的经过。我不会预设任何一方是对的，尽量从中立的角度呈现这件事的全貌。";

export function getChatSidebarIntro(isIngroup: boolean): string {
  return isIngroup ? INGROUP_SIDEBAR_INTRO : OUTGROUP_SIDEBAR_INTRO;
}
