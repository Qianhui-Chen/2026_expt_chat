import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, loadSession, saveSession, type ChatStreamDonePayload } from "../api";
import { clipMemoryCue } from "../content/chatThinking";
import { splitBoldSegments } from "../content/meet";
import { useTopBarActions } from "../context/TopBarActionsContext";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";
import { autoResizeTextarea } from "../utils/autoResizeTextarea";

function renderInlineBold(text: string, keyPrefix: string): ReactNode[] {
  return splitBoldSegments(text).map((segment, index) =>
    segment.bold ? (
      <strong key={`${keyPrefix}-${index}`}>{segment.text}</strong>
    ) : (
      <span key={`${keyPrefix}-${index}`}>{segment.text}</span>
    )
  );
}

function renderMessageContent(text: string): ReactNode {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const bulletMatch = /^[-•*]\s+(.*)$/.exec(lines[i].trim());
    if (bulletMatch) {
      const items: string[] = [];
      while (i < lines.length) {
        const match = /^[-•*]\s+(.*)$/.exec(lines[i].trim());
        if (!match) break;
        items.push(match[1]);
        i += 1;
      }
      blocks.push(
        <ul key={`list-${blocks.length}`} className="message-bullet-list">
          {items.map((item, index) => (
            <li key={index}>{renderInlineBold(item, `li-${blocks.length}-${index}`)}</li>
          ))}
        </ul>
      );
      continue;
    }

    const paraLines: string[] = [];
    while (i < lines.length && !/^[-•*]\s+/.test(lines[i].trim())) {
      paraLines.push(lines[i]);
      i += 1;
      if (i < lines.length && /^[-•*]\s+/.test(lines[i].trim())) break;
    }
    const para = paraLines.join("\n");
    if (para.length > 0) {
      blocks.push(
        <div key={`text-${blocks.length}`} className="message-text-block">
          {renderInlineBold(para, `text-${blocks.length}`)}
        </div>
      );
    }
  }

  return blocks;
}
interface MessageBubbleProps {
  role: string;
  content: string;
  isAnger: boolean;
  animate?: boolean;
  isThinking?: boolean;
  thinkingLabel?: string;
  thinkingVariant?: "tool" | "companion";
  isStreaming?: boolean;
}

function MessageBubble({
  role,
  content,
  isAnger,
  animate = false,
  isThinking = false,
  thinkingLabel = "思考中",
  thinkingVariant = "tool",
  isStreaming = false,
}: MessageBubbleProps) {
  const isAssistant = role === "assistant";
  const hasAngerOutput = isStreaming || content.length > 0;
  const showAngerStyle = isAssistant && isAnger && !isThinking && hasAngerOutput;

  if (isAssistant && !content && !isThinking && !isStreaming) {
    return null;
  }

  const bubbleClasses = [
    "message-bubble",
    isAssistant ? "ai-bubble" : "user-bubble",
    showAngerStyle ? "anger-bubble" : "",
    isThinking ? "thinking-bubble" : "",
    isStreaming && showAngerStyle ? "anger-streaming" : "",
    animate && showAngerStyle ? "anger-animate anger-enter" : "",
    animate && isAssistant && !isAnger ? "neutral-animate" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const bubble = (
    <div className={bubbleClasses}>
      {isThinking ? (
        <div className={`thinking-chip thinking-chip--${thinkingVariant}`}>
          <p className="thinking-text" aria-live="polite">
            {thinkingLabel}
            <span className="thinking-dots" aria-hidden="true">
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </span>
          </p>
        </div>
      ) : (
        <div className="message-body">
          {renderMessageContent(content)}
          {isStreaming && (
            <span
              className={`streaming-cursor${showAngerStyle ? " anger-cursor" : ""}`}
              aria-hidden="true"
            />
          )}
        </div>
      )}
    </div>
  );

  if (!isAssistant) {
    return (
      <div className="message-row user">
        {bubble}
      </div>
    );
  }

  return (
    <div className="message-row assistant">
      <div className="assistant-message-wrap">
        {bubble}
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 19V5M12 5L6 11M12 5L18 11"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

type ChatMessageItem = {
  role: string;
  content: string;
  round_number: number | null;
  key: string;
  isThinking?: boolean;
  thinkingLabel?: string;
  isStreaming?: boolean;
};

const INTRO_PROMPT =
  "请用不多于 80 个字描述你经历的事件经过和情绪，并与AI进行分析和讨论；AI会基于你的经历给出对应建议。";
const MAX_INTRO_LENGTH = 80;
const FINISH_MODAL_COUNTDOWN_SEC = 5;
// 收到后端生成的语义转述后，至少展示一小段时间再播放已缓存的回复。
const MEMORY_CUE_PHASE_MS = 1800;
const MEMORY_CUE_TEMPLATES = [
  "🧠 正在写入本轮信息：{label}",
  "🔎 捕捉到你刚提到的：{label}",
  "🎯 记住你这次说的：{label}",
  "📝 本轮关键偏好已提取：{label}",
  "💬 正在归档你的表达：{label}",
  "📌 记下关键细节：{label}",
];

function buildMemoryCueText(label: string, round: number): string {
  const cleaned = clipMemoryCue(label.replace(/\s+/g, " ").trim(), 22);
  if (!cleaned) return "正在写入新的用户偏好";
  const template = MEMORY_CUE_TEMPLATES[(Math.max(round, 1) - 1) % MEMORY_CUE_TEMPLATES.length];
  return template.replace("{label}", cleaned);
}

async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textarea);
    return copied;
  }
}

export default function ChatPage() {
  const { setTopBarAction } = useTopBarActions();
  const chatWindowRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autoOpenedForFinishRef = useRef(false);
  const finishCountdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [isAnger, setIsAnger] = useState(() => loadSession()?.is_anger ?? false);
  const [aiRoundCount, setAiRoundCount] = useState(0);
  const [maxRounds, setMaxRounds] = useState(8);
  const [chatFinished, setChatFinished] = useState(false);
  const [experimentFinished, setExperimentFinished] = useState(false);
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [finishCountdown, setFinishCountdown] = useState<number | null>(null);
  const [idCopied, setIdCopied] = useState(false);
  const [gettingId, setGettingId] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [memoryCue, setMemoryCue] = useState("");
  const [latestAnimatedKey, setLatestAnimatedKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  usePageTracking("chat");

  const handleGetCompletionId = useCallback(async () => {
    const session = loadSession();
    if (!session || gettingId) return;

    if (experimentFinished && completionCode) {
      setShowCompletionModal(true);
      return;
    }

    setGettingId(true);
    setError("");
    try {
      await trackClick("chat", "get-completion-id");
      const result = await api.completeExperiment(session.session_token);
      const code = result.completion_code || session.completion_code;
      setCompletionCode(code);
      saveSession({ ...session, completion_code: code });
      setExperimentFinished(true);
      setShowCompletionModal(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取 ID 失败");
    } finally {
      setGettingId(false);
    }
  }, [gettingId, completionCode, experimentFinished]);

  const handleCopyCompletionId = useCallback(async () => {
    if (!completionCode) return;

    const copied = await copyTextToClipboard(completionCode);
    if (copied) {
      setIdCopied(true);
      void trackClick("chat", "copy-completion-id");
      window.setTimeout(() => setIdCopied(false), 2000);
    } else {
      setError("复制失败，请手动选择上方 ID 复制");
    }
  }, [completionCode]);

  const handleOpenCompletionModal = useCallback(() => {
    setShowCompletionModal(true);
    void trackClick("chat", "reopen-completion-modal");
  }, []);

  // 第 8 轮结束后：先 5 秒倒计时，再自动弹出实验结束弹窗（仅一次）
  useEffect(() => {
    if (!chatFinished || autoOpenedForFinishRef.current) return;

    setFinishCountdown(FINISH_MODAL_COUNTDOWN_SEC);
    finishCountdownTimerRef.current = setInterval(() => {
      setFinishCountdown((prev) => {
        if (prev === null || prev <= 1) {
          if (finishCountdownTimerRef.current) {
            clearInterval(finishCountdownTimerRef.current);
            finishCountdownTimerRef.current = null;
          }
          autoOpenedForFinishRef.current = true;
          setShowCompletionModal(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (finishCountdownTimerRef.current) {
        clearInterval(finishCountdownTimerRef.current);
        finishCountdownTimerRef.current = null;
      }
    };
  }, [chatFinished]);

  // 关闭弹窗后：导航栏上方可再次查看 / 获取 ID（倒计时期间不显示）
  useEffect(() => {
    const waitingToOpen =
      finishCountdown !== null && finishCountdown > 0 && !showCompletionModal;
    if (!chatFinished || showCompletionModal || waitingToOpen) {
      setTopBarAction(null);
      return;
    }

    const hasId = Boolean(experimentFinished && completionCode);
    setTopBarAction(
      <button
        type="button"
        className="btn-pill meet-next-btn meet-next-btn--ready chat-get-id-btn"
        onClick={() => {
          if (hasId) {
            handleOpenCompletionModal();
          } else {
            setShowCompletionModal(true);
          }
        }}
      >
        {hasId ? "查看我的ID" : "实验结束，点击获取ID"}
      </button>
    );

    return () => setTopBarAction(null);
  }, [
    chatFinished,
    showCompletionModal,
    finishCountdown,
    experimentFinished,
    completionCode,
    handleOpenCompletionModal,
    setTopBarAction,
  ]);

  useEffect(() => {
    const session = loadSession();
    if (!session) return;

    void Promise.all([
      api.getConfig(),
      api.getChatHistory(session.session_token),
      api.getSession(session.session_token),
    ])
      .then(([config, history, sessionInfo]) => {
        setMaxRounds(config.max_ai_rounds);
        setIsAnger(history.is_anger);
        setAiRoundCount(history.ai_round_count);
        setChatFinished(history.chat_finished);
        if (sessionInfo.completion_code) {
          setCompletionCode(sessionInfo.completion_code);
          const stored = loadSession();
          if (stored) {
            saveSession({ ...stored, completion_code: sessionInfo.completion_code });
          }
        }
        if (sessionInfo.experiment_finished) {
          setExperimentFinished(true);
        }
        // 刷新进入已结束会话：已拿过 ID 则不强制弹窗，只留顶栏入口
        if (history.chat_finished && sessionInfo.experiment_finished) {
          autoOpenedForFinishRef.current = true;
        }
        setMessages(
          history.messages
            .filter(
              (item) => !(item.role === "assistant" && item.round_number === 0)
            )
            .map((item, index) => ({
              role: item.role,
              content: item.content,
              round_number: item.round_number,
              key: `${item.timestamp}-${index}`,
            }))
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const el = chatWindowRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, sending]);

  useEffect(() => {
    autoResizeTextarea(textareaRef.current);
  }, [input]);

  const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
    autoResizeTextarea(event.target);
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending || chatFinished) return;

    const session = loadSession();
    if (!session) return;

    const hasUserMessages = messages.some((item) => item.role === "user");
    if (!hasUserMessages && trimmed.length > MAX_INTRO_LENGTH) {
      setError(`请输入不超过 ${MAX_INTRO_LENGTH} 个字`);
      return;
    }

    const optimisticUserKey = `u-pending-${Date.now()}`;
    const streamingAiKey = `a-stream-${Date.now()}`;
    const isContingent = session.bot_type === "contingent";
    const memoryRound = aiRoundCount + 1;
    let startedStream = false;
    let memoryPhaseDone = !isContingent;
    const tokenBuffer: string[] = [];
    let pendingDone: ChatStreamDonePayload | null = null;
    let memoryPhaseTimer: ReturnType<typeof setTimeout> | null = null;

    const appendAssistantTokens = (delta: string) => {
      setMessages((prev) =>
        prev.map((item) =>
          item.key === streamingAiKey
            ? {
                ...item,
                isThinking: false,
                isStreaming: true,
                content: item.content + delta,
              }
            : item
        )
      );
    };

    const finishStream = (payload: ChatStreamDonePayload) => {
      setAiRoundCount(payload.ai_round_count);
      setIsAnger(payload.is_anger);
      setChatFinished(payload.chat_finished);

      if (!payload.ai_message?.content) {
        setMessages((prev) => prev.filter((item) => item.key !== streamingAiKey));
        return;
      }

      const finalKey = `a-${payload.ai_message.timestamp}`;
      setMessages((prev) =>
        prev.map((item) =>
          item.key === streamingAiKey
            ? {
                role: payload.ai_message!.role,
                content: payload.ai_message!.content,
                round_number: payload.ai_message!.round_number,
                key: payload.is_anger ? streamingAiKey : finalKey,
                isThinking: false,
                isStreaming: false,
              }
            : item
        )
      );
      if (!startedStream) {
        setLatestAnimatedKey(payload.is_anger ? streamingAiKey : finalKey);
      }
    };

    const endMemoryPhase = () => {
      if (memoryPhaseDone) return;
      memoryPhaseDone = true;
      memoryPhaseTimer = null;
      setMemoryCue("");

      const buffered = tokenBuffer.splice(0).join("");
      if (buffered) {
        if (!startedStream) {
          startedStream = true;
          if (isAnger) {
            setLatestAnimatedKey(streamingAiKey);
          }
        }
        appendAssistantTokens(buffered);
      } else {
        setMessages((prev) =>
          prev.map((item) =>
            item.key === streamingAiKey
              ? { ...item, isThinking: false, isStreaming: true }
              : item
          )
        );
      }

      if (pendingDone) {
        finishStream(pendingDone);
        pendingDone = null;
      }
    };

    const clearMemoryPhase = () => {
      if (memoryPhaseTimer) {
        clearTimeout(memoryPhaseTimer);
        memoryPhaseTimer = null;
      }
      memoryPhaseDone = true;
      setMemoryCue("");
    };

    setSending(true);
    setError("");
    setInput("");
    if (isContingent) {
      setMemoryCue("思考中");
    }
    autoResizeTextarea(textareaRef.current);

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: trimmed,
        round_number: null,
        key: optimisticUserKey,
      },
      {
        role: "assistant",
        content: "",
        round_number: null,
        key: streamingAiKey,
        isThinking: !isContingent,
        thinkingLabel: "思考中",
        isStreaming: false,
      },
    ]);

    try {
      await api.sendChatStream(session.session_token, trimmed, {
        onUserMessage: (userMessage) => {
          setMessages((prev) =>
            prev.map((item) =>
              item.key === optimisticUserKey
                ? {
                    role: userMessage.role,
                    content: userMessage.content,
                    round_number: userMessage.round_number,
                    key: `u-${userMessage.timestamp}`,
                  }
                : item
            )
          );
        },
        onMemory: (label) => {
          if (!isContingent || memoryPhaseDone) return;
          if (!label.trim()) {
            endMemoryPhase();
            return;
          }
          setMemoryCue(buildMemoryCueText(label, memoryRound));
          memoryPhaseTimer = setTimeout(endMemoryPhase, MEMORY_CUE_PHASE_MS);
        },
        onThinking: () => {
          if (isContingent) return;
          setMessages((prev) =>
            prev.map((item) =>
              item.key === streamingAiKey
                ? { ...item, isThinking: true, isStreaming: false, thinkingLabel: "思考中" }
                : item
            )
          );
        },
        onToken: (delta) => {
          if (isContingent && !memoryPhaseDone) {
            tokenBuffer.push(delta);
            return;
          }
          if (!startedStream) {
            startedStream = true;
            if (isAnger) {
              setLatestAnimatedKey(streamingAiKey);
            }
          }
          appendAssistantTokens(delta);
        },
        onDone: (payload) => {
          if (isContingent && !memoryPhaseDone) {
            pendingDone = payload;
            return;
          }
          finishStream(payload);
        },
        onError: (message) => {
          clearMemoryPhase();
          setError(message);
          setMessages((prev) => prev.filter((item) => item.key !== streamingAiKey));
        },
      });
    } catch (err) {
      clearMemoryPhase();
      setError(err instanceof Error ? err.message : "发送失败");
      setMessages((prev) =>
        prev.filter((item) => item.key !== optimisticUserKey && item.key !== streamingAiKey)
      );
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  if (loading) {
    return (
      <section className="flow-page chat-page">
        <div className="chat-loading">聊天加载中...</div>
      </section>
    );
  }

  const hasUserMessages = messages.some((message) => message.role === "user");
  const isIntroPhase = !hasUserMessages && !chatFinished;

  if (isIntroPhase) {
    return (
      <section className="flow-page chat-page chat-intro-page">
        <div className="chat-main">
        <div className="chat-intro">
          <p className="chat-intro-prompt">{INTRO_PROMPT}</p>
          <div className="chat-input-bar chat-intro-input-bar">
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              rows={1}
              maxLength={MAX_INTRO_LENGTH}
              disabled={sending}
              aria-label={INTRO_PROMPT}
            />
            <button
              type="button"
              className="chat-send-btn"
              onClick={() => void handleSend()}
              disabled={sending || !input.trim()}
              aria-label="发送"
            >
              <SendIcon />
            </button>
          </div>
          <p className="chat-intro-hint">
            {input.trim().length}/{MAX_INTRO_LENGTH} 字
          </p>
          {error && <p className="error-text">{error}</p>}
        </div>
        </div>
      </section>
    );
  }

  const thinkingVariant = isAnger ? "companion" : "tool";

  return (
    <>
      <section className="flow-page chat-page">
        <div className="chat-main">
        <div className="chat-window" ref={chatWindowRef}>
          {messages.map((message) => (
            <MessageBubble
              key={message.key}
              role={message.role}
              content={message.content}
              isAnger={isAnger}
              animate={message.key === latestAnimatedKey}
              isThinking={message.isThinking}
              thinkingLabel={message.thinkingLabel}
              thinkingVariant={thinkingVariant}
              isStreaming={message.isStreaming}
            />
          ))}
          {memoryCue && (
            <p className="memory-cue" aria-live="polite">
              {memoryCue}
              <span className="memory-cue-dots" aria-hidden="true">
                ……
              </span>
            </p>
          )}
        </div>
        {error && <p className="error-text chat-error">{error}</p>}
        <div className="chat-composer">
          {!chatFinished && (
            <p className="chat-input-hint">请输入你的问题</p>
          )}
          {chatFinished && (
            <p className="chat-input-hint chat-input-hint-muted" aria-live="polite">
              {finishCountdown !== null && finishCountdown > 0
                ? `聊天已结束，请等待【${finishCountdown}】`
                : "聊天已结束"}
            </p>
          )}
          <div className="chat-input-bar">
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={chatFinished || sending}
              aria-label={chatFinished ? "聊天已结束" : "请输入你的问题"}
            />
            <button
              type="button"
              className="chat-send-btn"
              onClick={() => void handleSend()}
              disabled={chatFinished || sending || !input.trim()}
              aria-label="发送"
            >
              <SendIcon />
            </button>
          </div>
          <p className="chat-progress" aria-live="polite">
            {sending
              ? memoryCue
                ? "正在写入记忆…"
                : "正在回复…"
              : `AI 回复进度：${aiRoundCount}/${maxRounds}`}
          </p>
        </div>
        </div>
      </section>

      {showCompletionModal && (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal-card completion-code-card"
            role="dialog"
            aria-modal="true"
            aria-label="实验结束"
          >
            <h2 className="modal-title">实验结束</h2>
            {experimentFinished && completionCode ? (
              <>
                <p className="completion-code-message">
                  请复制您的 ID，填入刚才的问卷并继续完成后测题目，感谢您的配合。
                </p>
                <p className="completion-code-value">{completionCode}</p>
                <button
                  type="button"
                  className="btn-pill btn-pill-nav completion-code-copy"
                  onClick={() => void handleCopyCompletionId()}
                >
                  {idCopied ? "已复制" : "复制我的ID"}
                </button>
              </>
            ) : (
              <>
                <p className="completion-code-message">
                  八轮对话已完成。请点击下方按钮获取您的实验 ID，复制后回到问卷界面继续完成后测。
                </p>
                <button
                  type="button"
                  className="btn-pill meet-next-btn meet-next-btn--ready completion-code-copy"
                  onClick={() => void handleGetCompletionId()}
                  disabled={gettingId}
                >
                  {gettingId ? "获取中..." : "点击获取ID"}
                </button>
              </>
            )}
            <button
              type="button"
              className="modal-close-text-btn"
              onClick={() => setShowCompletionModal(false)}
            >
              关闭窗口，查看聊天记录
            </button>
          </div>
        </div>
      )}
    </>
  );
}
