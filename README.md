# Anger Experiment Platform

基于 `实验pipeline.md` 实现的前后端分离实验平台。

## 功能

- 用户 ID 登录与 4 种实验条件自动分配（A/B + 奇偶数）
- 5 步流程：登录 → 知情同意 → 说明 → 聊天 → 后测问卷
- 全程记录：点击行为、页面停留时间、聊天记录、时间戳
- DeepSeek 驱动聊天，固定 AI 开场白
- A 组愤怒 UI：AI 回复 4 秒 💢 + 抖动动画
- 第 6 轮 AI 回复后弹出「试验结束」
- 提示词按轮次分 early / final；**立场（aligned / ambiguous）在第 6 轮有强化版**，见 [docs/PROMPTS.md](docs/PROMPTS.md)

## 项目结构

```
anger_2026/
├── backend/          # Python FastAPI
├── docs/
│   └── PROMPTS.md    # AI 提示词完整说明（含立场 early/final）
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

浏览器打开：http://localhost:5173

## 测试 ID

| ID | 条件 |
|----|------|
| A1 | 愤怒 + 立场一致 |
| A2 | 愤怒 + 立场模糊 |
| B1 | 中性 + 立场一致 |
| B2 | 中性 + 立场模糊 |

## 问卷链接

在 `frontend/src/config.ts` 中配置：

```
CONSENT_SURVEY_URL  — 知情同意问卷
POST_SURVEY_URL     — 后测问卷
```

## 数据存储

SQLite 默认保存在 `backend/experiment.db`，包含：

- `user_sessions`：用户与条件
- `click_events`：点击行为
- `page_events`：页面停留
- `chat_messages`：聊天记录

## API 概览

- `POST /api/login`
- `GET /api/session/{id}`
- `POST /api/events/click`
- `POST /api/events/page-leave`
- `GET /api/chat/{session_token}`
- `POST /api/chat/send`
- `GET /api/config`
