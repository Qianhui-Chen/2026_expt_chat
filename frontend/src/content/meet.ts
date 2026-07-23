/** MeetYourBot：按 bot_type（奇数 tool / 偶数 companion）分支 */

import { publicAsset } from "../utils/publicAsset";

export const MEET_CLICK_CARD_HINT = "点击卡片以进行下一步";

/** 扇形叠放阶段的卡牌数 */
export const MEET_FAN_CARD_COUNT = 3;
/** 点击展开后：上 1 + 下 3 */
export const MEET_EXPANDED_CARD_COUNT = 4;

/** 奇数组 Tool 卡牌正面图（放入 frontend/public/meet/） */
export const MEET_TOOL_CARD_IMAGE = publicAsset("meet/tool_icon.png");

/** 偶数组 Companion 卡牌正面图（放入 frontend/public/meet/） */
export const MEET_COMPANION_CARD_IMAGE = publicAsset("meet/Companion_icon.png");

export const MEET_TOOL_CARD_LABEL = "工具型AI";
export const MEET_COMPANION_CARD_LABEL = "陪伴型AI";

export type MeetPanelCopy = {
  title: string;
  lines: string[];
};

/** 展开后文案（**text** 表示加粗） */
export type MeetExpandedCopy = {
  /** 上方主卡文案 */
  heroLines: string[];
  /** 主卡与下方三卡之间的中间文案 */
  midLines: string[];
  /** 下方左 / 中 / 右三张卡 */
  panels: [MeetPanelCopy, MeetPanelCopy, MeetPanelCopy];
};

export const MEET_TOOL_EXPANDED: MeetExpandedCopy = {
  heroLines: ["和你聊天的模型", "主要以**高效协作**为训练目标"],
  midLines: [
    "这一模型主要被训练用于完成复杂推理任务，是高效的协作工具，擅长创作、推理和协作。在对话中，和许多AI产品类似，它能够**帮助你分析情况**，也会**提供建议**。",
  ],
  panels: [
    {
      title: "训练数据",
      lines: ["√ 主打顶级任务处理性能", "√ 超长上下文", "√ 总参数1.6T"],
    },
    {
      title: "擅长任务",
      lines: [
        "创意 ：  ✍    ✍    ✍    ✍    ✍",
        "推理 ： ⚡   ⚡   ⚡   ⚡   ⚡",
        "编程 ： 💡   💡   💡   💡   💡",
      ],
    },
    {
      title: "应用场景",
      lines: ["√ 复杂编程任务", "√ 邮件整理与写作", "√ 信息检索总结", "√ ……"],
    },
  ],
};

export const MEET_COMPANION_EXPANDED: MeetExpandedCopy = {
  heroLines: ["和你聊天的模型", "主要以**支持陪伴**为训练目标"],
  midLines: [
    "这一模型主要被训练用于陪伴和情感支持，有着自己独特的个性和背景故事，擅长共情和情绪支持。在对话中，它能够**感受你的情绪**，也会**表达自己的感受**。",
  ],
  panels: [
    {
      title: "训练数据",
      lines: [
        "√ 千万条真实人类对话数据集",
        "√ 理解数十种人类情绪",
        "√ 情景理解能力",
      ],
    },
    {
      title: "擅长任务",
      lines: [
        "陪伴 ： ❤️   ❤️   ❤️   ❤️   ❤️",
        "倾听 ： 👂   👂   👂   👂   👂",
        "理解 ： 💡   💡   💡   💡"
      ],
    },
    {
      title: "应用场景",
      lines: ["√ 倾诉与陪伴", "√ 人际意见获取", "√ 简单基础心理疏导", "√ ……"],
    },
  ],
};

export function getMeetExpandedCopy(botType: "tool" | "companion"): MeetExpandedCopy {
  return botType === "companion" ? MEET_COMPANION_EXPANDED : MEET_TOOL_EXPANDED;
}

/** 将 `**加粗**` 转为片段，供 JSX 渲染 */
export function splitBoldSegments(text: string): { bold: boolean; text: string }[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((part) => {
    const match = /^\*\*([^*]+)\*\*$/.exec(part);
    if (match) {
      return { bold: true, text: match[1] };
    }
    return { bold: false, text: part };
  });
}
