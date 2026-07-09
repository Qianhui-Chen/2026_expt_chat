import { useCallback, useEffect, useRef, useState } from "react";
import { api, loadSession, saveSession } from "../api";
import { useTopBarActions } from "../context/TopBarActionsContext";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";
import { MAX_ANGER_METER, getAngerMeterLevel, getPendingAngerMeterLevel } from "../utils/angerMeter";
import { autoResizeTextarea } from "../utils/autoResizeTextarea";

interface MessageBubbleProps {
  role: string;
  content: string;
  isAnger: boolean;
  animate?: boolean;
  isThinking?: boolean;
  isStreaming?: boolean;
  angerLevel?: number;
  maxAngerMeter?: number;
}

function MessageBubble({
  role,
  content,
  isAnger,
  animate = false,
  isThinking = false,
  isStreaming = false,
  angerLevel = 0,
  maxAngerMeter = MAX_ANGER_METER,
}: MessageBubbleProps) {
  const isAssistant = role === "assistant";
  const hasAngerOutput = isStreaming || content.length > 0;
  const showAngerStyle = isAssistant && isAnger && !isThinking && hasAngerOutput;
  const showMeter = showAngerStyle && angerLevel > 0;
  const meterPercent = Math.min(Math.round((angerLevel / maxAngerMeter) * 100), 100);

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

  const showAngerEmojis = showAngerStyle;

  const bubble = (
    <div className={bubbleClasses}>
      {showAngerEmojis && (
        <>
          <span className="anger-emoji anger-emoji-tr anger-emoji-lg" aria-hidden="true">💢</span>
          <span className="anger-emoji anger-emoji-tr anger-emoji-sm" aria-hidden="true">💢</span>
          <span className="anger-emoji anger-emoji-bl anger-emoji-lg" aria-hidden="true">💢</span>
          <span className="anger-emoji anger-emoji-bl anger-emoji-sm" aria-hidden="true">💢</span>
        </>
      )}
      {isThinking ? (
        <p className="thinking-text" aria-live="polite">
          AI 正在思考
          <span className="thinking-dots" aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </p>
      ) : (
        <p>
          {content}
          {isStreaming && (
            <span
              className={`streaming-cursor${showAngerStyle ? " anger-cursor" : ""}`}
              aria-hidden="true"
            />
          )}
        </p>
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
        {showMeter && (
          <div className="anger-meter" aria-hidden="true">
            <span className="anger-meter-label">情绪强度</span>
            <div className="anger-meter-track">
              <div className="anger-meter-fill" style={{ width: `${meterPercent}%` }} />
            </div>
            <span className="anger-meter-value">
              {angerLevel}/{maxAngerMeter}
            </span>
          </div>
        )}
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
  isStreaming?: boolean;
};

const INTRO_PROMPT = "请用不多于 80 个字描述你经历的事件内容、感受和情绪，并与AI进行分析和讨论；AI会基于你的经历给出对应建议。";
const MAX_INTRO_LENGTH = 80;
const NEXT_STEP_COUNTDOWN_SEC = 8;

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
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [isAnger, setIsAnger] = useState(false);
  const [aiRoundCount, setAiRoundCount] = useState(0);
  const [maxRounds, setMaxRounds] = useState(6);
  const [chatFinished, setChatFinished] = useState(false);
  const [experimentFinished, setExperimentFinished] = useState(false);
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [idCopied, setIdCopied] = useState(false);
  const [nextStepCountdown, setNextStepCountdown] = useState<number | null>(null);
  const [nextStepSubmitting, setNextStepSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [latestAnimatedKey, setLatestAnimatedKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  usePageTracking("chat");

  const handleNextStep = useCallback(async () => {
    const session = loadSession();
    if (!session || nextStepCountdown !== 0 || nextStepSubmitting) return;

    setNextStepSubmitting(true);
    setError("");
    try {
      await trackClick("chat", "next-step");
      if (experimentFinished && completionCode) {
        setShowCompletionModal(true);
        return;
      }
      const result = await api.completeExperiment(session.session_token);
      const code = result.completion_code || session.completion_code;
      setCompletionCode(code);
      saveSession({ ...session, completion_code: code });
      setExperimentFinished(true);
      setShowCompletionModal(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setNextStepSubmitting(false);
    }
  }, [nextStepCountdown, nextStepSubmitting, completionCode, experimentFinished]);

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

  useEffect(() => {
    if (!chatFinished) {
      setNextStepCountdown(null);
      return;
    }

    if (experimentFinished) {
      setNextStepCountdown(0);
      return;
    }

    setNextStepCountdown(NEXT_STEP_COUNTDOWN_SEC);
    countdownTimerRef.current = setInterval(() => {
      setNextStepCountdown((prev) => {
        if (prev === null || prev <= 1) {
          if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
            countdownTimerRef.current = null;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
    };
  }, [chatFinished, experimentFinished]);

  useEffect(() => {
    if (!chatFinished || nextStepCountdown === null) {
      setTopBarAction(null);
      return;
    }

    const ready = nextStepCountdown === 0 && !nextStepSubmitting;
    const label =
      nextStepSubmitting
        ? "跳转中..."
        : nextStepCountdown > 0
          ? `下一步 (${nextStepCountdown})`
          : "下一步";

    setTopBarAction(
      <button
        type="button"
        className={`btn-pill btn-pill-next-step${ready ? " btn-pill-next-step-ready" : ""}`}
        onClick={() => void handleNextStep()}
        disabled={!ready}
      >
        {label}
      </button>
    );

    return () => setTopBarAction(null);
  }, [chatFinished, nextStepCountdown, nextStepSubmitting, handleNextStep, setTopBarAction]);

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

    setSending(true);
    setError("");
    setInput("");
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
        isThinking: true,
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
        onThinking: () => {
          setMessages((prev) =>
            prev.map((item) =>
              item.key === streamingAiKey
                ? { ...item, isThinking: true, isStreaming: false, content: "" }
                : item
            )
          );
        },
        onToken: (delta) => {
          let shouldTriggerAngerAnimate = false;
          setMessages((prev) => {
            const streaming = prev.find((item) => item.key === streamingAiKey);
            shouldTriggerAngerAnimate = Boolean(streaming?.isThinking && isAnger);
            return prev.map((item) =>
              item.key === streamingAiKey
                ? {
                    ...item,
                    isThinking: false,
                    isStreaming: true,
                    content: item.content + delta,
                  }
                : item
            );
          });
          if (shouldTriggerAngerAnimate) {
            setLatestAnimatedKey(streamingAiKey);
          }
        },
        onDone: (payload) => {
          setAiRoundCount(payload.ai_round_count);
          setIsAnger(payload.is_anger);
          setChatFinished(payload.chat_finished);

          if (payload.ai_message) {
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
            if (payload.is_anger) {
              setLatestAnimatedKey(streamingAiKey);
            } else {
              setLatestAnimatedKey(finalKey);
            }
          } else {
            setMessages((prev) => prev.filter((item) => item.key !== streamingAiKey));
          }

        },
        onError: (message) => {
          setError(message);
          setMessages((prev) => prev.filter((item) => item.key !== streamingAiKey));
        },
      });
    } catch (err) {
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
      </section>
    );
  }

  const sessionToken = loadSession()?.session_token ?? 0;

  const getAngerLevel = (message: ChatMessageItem) => {
    if (!isAnger || message.role !== "assistant" || !sessionToken) return 0;

    if (message.round_number && message.round_number > 0) {
      return getAngerMeterLevel(message.round_number, sessionToken);
    }

    if (message.isStreaming) {
      const nextRound = aiRoundCount + 1;
      return getPendingAngerMeterLevel(nextRound, sessionToken);
    }

    return 0;
  };

  return (
    <>
      <section className="flow-page chat-page">
        <div className="chat-window" ref={chatWindowRef}>
          {messages.map((message) => (
            <MessageBubble
              key={message.key}
              role={message.role}
              content={message.content}
              isAnger={isAnger}
              animate={message.key === latestAnimatedKey}
              isThinking={message.isThinking}
              isStreaming={message.isStreaming}
              angerLevel={getAngerLevel(message)}
              maxAngerMeter={MAX_ANGER_METER}
            />
          ))}
        </div>
        {error && <p className="error-text chat-error">{error}</p>}
        <div className="chat-composer">
          {!chatFinished && (
            <p className="chat-input-hint">请输入你的问题</p>
          )}
          {chatFinished && (
            <p className="chat-input-hint chat-input-hint-muted">聊天已结束</p>
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
            {sending ? "AI 正在思考…" : `AI 回复进度：${aiRoundCount}/${maxRounds}`}
          </p>
        </div>
      </section>

      {showCompletionModal && completionCode && (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal-card completion-code-card"
            role="dialog"
            aria-modal="true"
            aria-label="完成代码"
          >
            <p className="completion-code-message">
              请复制您的ID，填入刚才的问卷，并且完成后测题目，感谢您的配合。
            </p>
            <p className="completion-code-value">{completionCode}</p>
            <button
              type="button"
              className="btn-pill btn-pill-nav completion-code-copy"
              onClick={() => void handleCopyCompletionId()}
            >
              {idCopied ? "已复制" : "复制我的ID"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
