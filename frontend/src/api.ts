export interface SessionState {
  session_token: number;
  attempt_number: number;
  is_anger: boolean;
  bot_type: "tool" | "companion";
  completion_code: string;
}

export interface SessionResponse {
  attempt_number: number;
  is_anger: boolean;
  bot_type: "tool" | "companion";
  ai_round_count: number;
  chat_finished: boolean;
  experiment_finished: boolean;
  completion_code: string;
}

export interface ChatMessageDTO {
  role: string;
  content: string;
  round_number: number | null;
  timestamp: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessageDTO[];
  ai_round_count: number;
  chat_finished: boolean;
  is_anger: boolean;
}

export interface ChatSendResponse {
  user_message: ChatMessageDTO;
  ai_message: ChatMessageDTO | null;
  ai_round_count: number;
  chat_finished: boolean;
  is_anger: boolean;
}

export interface ChatStreamDonePayload {
  ai_message: ChatMessageDTO | null;
  ai_round_count: number;
  chat_finished: boolean;
  is_anger: boolean;
}

export interface ChatStreamCallbacks {
  onUserMessage?: (message: ChatMessageDTO) => void;
  onThinking?: () => void;
  onToken?: (delta: string) => void;
  onDone?: (payload: ChatStreamDonePayload) => void | Promise<void>;
  onError?: (message: string) => void;
}

export interface AppConfig {
  max_ai_rounds: number;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "请求失败" }));
    const detail = data.detail;
    if (typeof detail === "string") {
      throw new Error(detail);
    }
    if (Array.isArray(detail) && detail.length > 0) {
      throw new Error(detail.map((item: { msg?: string }) => item.msg ?? "请求失败").join("；"));
    }
    throw new Error(`请求失败（HTTP ${response.status}）`);
  }
  return response.json() as Promise<T>;
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  const lines = block.split("\n");
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return { event, data: dataLines.join("\n") };
}

export const api = {
  getConfig: () => request<AppConfig>("/api/config"),
  startSession: () =>
    request<SessionState>("/api/session/start", {
      method: "POST",
    }),
  getSession: (session_token: number) =>
    request<SessionResponse>(`/api/session/${session_token}`),
  completeExperiment: (session_token: number) =>
    request<{ ok: boolean; completion_code: string }>("/api/experiment/complete", {
      method: "POST",
      body: JSON.stringify({ session_token }),
    }),
  logClick: (session_token: number, page: string, element: string) =>
    request<{ ok: boolean }>("/api/events/click", {
      method: "POST",
      body: JSON.stringify({ session_token, page, element }),
    }),
  logPageLeave: (
    session_token: number,
    page: string,
    entered_at: string,
    left_at: string
  ) =>
    request<{ ok: boolean; dwell_ms: number }>("/api/events/page-leave", {
      method: "POST",
      body: JSON.stringify({ session_token, page, entered_at, left_at }),
    }),
  getChatHistory: (session_token: number) =>
    request<ChatHistoryResponse>(`/api/chat/${session_token}`),
  sendChat: (session_token: number, message: string) =>
    request<ChatSendResponse>("/api/chat/send", {
      method: "POST",
      body: JSON.stringify({ session_token, message }),
    }),
  sendChatStream: async (
    session_token: number,
    message: string,
    callbacks: ChatStreamCallbacks,
    signal?: AbortSignal
  ) => {
    const response = await fetch("/api/chat/send-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_token, message }),
      signal,
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({ detail: "请求失败" }));
      const detail = data.detail;
      const messageText =
        typeof detail === "string"
          ? detail
          : `请求失败（HTTP ${response.status}）`;
      callbacks.onError?.(messageText);
      throw new Error(messageText);
    }

    if (!response.body) {
      const err = "流式响应不可用";
      callbacks.onError?.(err);
      throw new Error(err);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        if (!block.trim()) {
          continue;
        }

        const parsed = parseSseBlock(block);
        if (!parsed) {
          continue;
        }

        const payload = JSON.parse(parsed.data) as Record<string, unknown>;

        switch (parsed.event) {
          case "user_message": {
            const userMsg = JSON.parse(parsed.data) as ChatMessageDTO;
            callbacks.onUserMessage?.(userMsg);
            break;
          }
          case "thinking":
            callbacks.onThinking?.();
            break;
          case "token":
            callbacks.onToken?.(String(payload.delta ?? ""));
            break;
          case "done": {
            const donePayload = JSON.parse(parsed.data) as ChatStreamDonePayload;
            await callbacks.onDone?.(donePayload);
            break;
          }
          case "error": {
            const messageText = String(payload.message ?? "请求失败");
            callbacks.onError?.(messageText);
            throw new Error(messageText);
          }
          default:
            break;
        }
      }
    }
  },
};

export const SESSION_KEY = "anger_experiment_session";

export function saveSession(data: SessionState) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(data));
  window.dispatchEvent(new Event("anger-session-updated"));
}

export function loadSession(): SessionState | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as SessionState;
    return {
      ...parsed,
      bot_type: normalizeBotType(parsed.bot_type, parsed.completion_code),
    };
  } catch {
    return null;
  }
}

/** 优先用后端 bot_type；缺失时按完成码奇偶推断（奇 tool / 偶 companion） */
export function normalizeBotType(
  botType: string | undefined,
  completionCode: string | undefined
): "tool" | "companion" {
  if (botType === "tool" || botType === "companion") {
    return botType;
  }
  const number = Number.parseInt((completionCode ?? "").slice(1), 10);
  if (Number.isFinite(number)) {
    return number % 2 === 1 ? "tool" : "companion";
  }
  return "tool";
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  window.dispatchEvent(new Event("anger-session-updated"));
}

function isSessionMissingError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err ?? "");
  return /会话不存在|HTTP 404|404/.test(message);
}

export async function ensureActiveSession(): Promise<SessionState> {
  const existing = loadSession();
  if (existing) {
    try {
      const data = await api.getSession(existing.session_token);
      if (!data.experiment_finished) {
        const session: SessionState = {
          session_token: existing.session_token,
          attempt_number: data.attempt_number,
          is_anger: data.is_anger,
          bot_type: normalizeBotType(data.bot_type, data.completion_code),
          completion_code: data.completion_code,
        };
        saveSession(session);
        return session;
      }
      clearSession();
    } catch (err) {
      // 仅会话真正不存在时丢弃本地；网络/代理抖动时继续用本地 session，避免底部闪「请求失败」
      if (isSessionMissingError(err)) {
        clearSession();
      } else {
        return {
          ...existing,
          bot_type: normalizeBotType(existing.bot_type, existing.completion_code),
        };
      }
    }
  }

  const started = await api.startSession();
  const normalized: SessionState = {
    ...started,
    bot_type: normalizeBotType(started.bot_type, started.completion_code),
  };
  saveSession(normalized);
  return normalized;
}
