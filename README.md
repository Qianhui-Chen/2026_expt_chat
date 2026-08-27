# Anger Experiment Platform

基于 `实验pipeline.md` 实现的前后端分离实验平台。

## 功能

- 被试进入说明页时自动随机分组（四组人数平衡）
- 流程：说明 → 聊天 → 结束后复制完成代码至问卷
- 全程记录：点击行为、页面停留时间、聊天记录、时间戳
- DeepSeek 驱动聊天
- A 组愤怒 UI：AI 回复 💢
- 8 轮结束后倒计时，点击「下一步」弹窗显示完成代码
- 提示词按组别（ingroup / outgroup）× 建议风格（generic / contingent）分支，见 [docs/PROMPTS.md](docs/PROMPTS.md)

## 项目结构

```
anger_2026/
├── backend/          # Python FastAPI
├── docs/
│   └── PROMPTS.md    # AI 提示词完整说明
└── frontend/         # React + TypeScript + Vite
```

## 启动方式

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

编辑 `.env`，填入 `DEEPSEEK_API_KEY`。未配置时会使用模拟回复，便于本地调试 UI。

```bash
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：http://localhost:5173（默认进入 `#/instruction`）

## 实验条件与完成代码

被试进入说明页时分配完成代码（人数平衡），完成代码示例：

| 完成代码 | emotion（组别） | position / advice_style（建议风格） |
|----------|-----------------|-------------------------------------|
| `A` + 奇数（如 A001） | ingroup | generic |
| `A` + 偶数（如 A002） | ingroup | contingent |
| `B` + 奇数（如 B001） | outgroup | generic |
| `B` + 偶数（如 B002） | outgroup | contingent |

流程：`#/instruction`（Welcome + 统一说明，无导航栏）→ `#/chat`。聊天结束后，被试在弹窗中复制该代码填写至 Credamo 后测问卷。

前端静态资源使用相对路径（`vite.base = "./"`），可直接把 `frontend/dist` 放到朋友服务器子目录，避免图片写成站根绝对路径后裂图。

## 数据存储

SQLite 默认保存在 `backend/experiment.db`。

### 为什么自变量在 `user_sessions` 而不是 `chat_messages`？

`emotion` 与 `position`（建议风格）是**被试层面**（between-subjects）的自变量，每名被试整场实验只有一个值。因此编码写在 **`user_sessions`** 表；`chat_messages` 通过 `session_id` 关联到同一会话。分析聊天内容时，将两表按 `session_id` 合并即可。

### 表结构概要

#### `user_sessions`（每名被试一条）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 会话主键（`session_token`） |
| `completion_code` | TEXT | 完成代码，如 `A001` |
| **`emotion`** | **INTEGER** | **组别自变量：0 = ingroup，1 = outgroup** |
| **`position`** | **INTEGER** | **建议风格：0 = generic，1 = contingent** |
| `emotion_label` | TEXT | 内部用：`ingroup` / `outgroup` |
| `position_label` | TEXT | 内部用：`generic` / `contingent` |
| `user_profile` | TEXT | 偶数组结构化用户画像 JSON；奇数组为空 |
| `ai_round_count` | INTEGER | AI 回复轮数 |
| `chat_finished` | INTEGER | 聊天是否结束 |
| `experiment_finished` | INTEGER | 实验是否完成 |
| `created_at` | DATETIME | 创建时间 |

#### `chat_messages`（每条消息一行）

| 字段 | 说明 |
|------|------|
| `session_id` | 关联 `user_sessions.id` |
| `role` | `user` / `assistant` |
| `content` | 消息正文 |
| `round_number` | AI 轮次（用户消息可为空） |
| `timestamp` | 时间戳 |

#### `click_events` / `page_events`

点击与页面停留记录，均通过 `session_id` 关联会话。

### 导出示例（SQL）

```sql
SELECT
  s.id AS session_id,
  s.completion_code,
  s.emotion,
  s.position,
  m.role,
  m.content,
  m.round_number,
  m.timestamp
FROM chat_messages m
JOIN user_sessions s ON s.id = m.session_id
ORDER BY s.id, m.timestamp;
```

## API 概览

- `POST /api/session/start` — 创建会话并随机分组
- `GET /api/session/{id}` — 查询会话状态
- `POST /api/experiment/complete` — 标记实验完成，返回 `completion_code`
- `POST /api/events/click`
- `POST /api/events/page-leave`
- `GET /api/chat/{session_token}`
- `POST /api/chat/send-stream`
- `GET /api/config`
