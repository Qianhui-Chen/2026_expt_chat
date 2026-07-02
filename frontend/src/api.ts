export interface LoginResponse {
  session_token: number;
  user_id: string;
  attempt_number: number;
  emotion: string;
  position: string;
  is_anger: boolean;
}

export interface SessionResponse {
  user_id: string;
  attempt_number: number;
  emotion: string;
  position: string;
  is_anger: boolean;
  ai_round_count: number;
  chat_finished: boolean;
  experiment_finished: boolean;
  has_similar_experience: boolean | null;
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
  onDone?: (payload: ChatStreamDonePayload) => void;
  onError?: (message: string) => void;
}

export interface AppConfig {
  max_ai_rounds: number;
}

export interface InstructionScreeningResponse {
  ok: boolean;
  continue_experiment: boolean;
  exit_reason: string | null;
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
  submitInstructionScreening: (session_token: number, has_similar_experience: boolean) =>
    request<InstructionScreeningResponse>("/api/instruction/screening", {
      method: "POST",
      body: JSON.stringify({ session_token, has_similar_experience }),
    }),
  login: (user_id: string) =>
    request<LoginResponse>("/api/login", {
      method: "POST",
      body: JSON.stringify({ user_id }),
    }),
  getSession: (session_token: number) =>
    request<SessionResponse>(`/api/session/${session_token}`),
  completeExperiment: (session_token: number) =>
    request<{ ok: boolean; attempt_number: number }>("/api/experiment/complete", {
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
            callbacks.onDone?.(donePayload);
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

export function saveSession(data: LoginResponse) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

export function loadSession(): LoginResponse | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LoginResponse;
  } catch {
    return null;
  }
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}
