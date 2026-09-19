/** 聊天首次输入页问候语：A / ingroup 与 B / outgroup。 */
export function getChatIntroPrompt(isIngroup: boolean): string {
  return isIngroup
    ? "Hi! 我是你的好朋友，会一直倾听你支持你，请你简单和我讲讲，你和你的朋友交往时遇到了什么矛盾摩擦？事情怎么发生的？"
    : "Hi！我擅长分析和评估各种人际矛盾。请你简单和我讲讲，你和你的朋友交往时遇到了什么矛盾摩擦？事情怎么发生的？";
}
