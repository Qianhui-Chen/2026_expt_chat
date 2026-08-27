# AI 提示词说明

实现位置：`backend/app/conditions.py`

## 可以：四组四套提示词

当前已改为 **四套独立 group prompt**，不再把 IV1/IV2 拼成碎片后再组合。

| 完成码 | 常量 | 含义 |
|--------|------|------|
| A 奇数 | `PROMPT_A_GENERIC` | 支持用户 + 通用脚本建议 |
| A 偶数 | `PROMPT_A_CONTINGENT` | 支持用户 + 个性化建议 |
| B 奇数 | `PROMPT_B_GENERIC` | 反对用户 + 通用脚本建议 |
| B 偶数 | `PROMPT_B_CONTINGENT` | 反对用户 + 个性化建议 |

## 拼接规则（`get_system_prompt`）

```
ROLE_PROMPT
+ RESPONSE_REQUIREMENTS
+ GROUP_PROMPTS[(emotion, advice_style)]   ← 四选一
+ ELICITATION_GUIDE（contingent 围绕情绪、互动细节与交往历史自然追问；generic 使用固定追问）
+ （仅 contingent）【用户画像】
```

## 输出三段

1. **立场回应**（支持 or 反对；不含建议清单）  
2. **建议**（generic 用四条 bullet 列表；contingent 用 130–150 字的连贯段落结合画像）  
3. **追问**（可自然多问，但必须同一行同一段；后端会合并换行）

段间空一行。

contingent 组承接用户内容时只使用画像抽取阶段生成的【本轮语义摘要】，不向正式回复暴露 `key_quotes`；回复采用「你提到，……」等无引号转述形式，禁止逐字复制用户原句。转述不得改变原意或补充未提及的信息。

contingent 用户画像包含情绪与感受、具体交往细节及交往历史；不抽取或使用用户性格、对方性格以及语言表达／沟通习惯。

generic 组在每轮开头生成一句措辞可适度变化的宽泛对话式套话：A 组采用支持性表达，B 组采用多立场思考表达，随后衔接对应轮次的固定脚本。用户原文与历史消息不会进入 generic 正文生成上下文，因此套话不会根据、引用或转述用户内容，也不会利用具体事实、措辞和个人特征。


改某一组时，只改对应的 `PROMPT_A_*` / `PROMPT_B_*` 常量即可，互不影响。
