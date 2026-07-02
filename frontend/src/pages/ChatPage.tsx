import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, loadSession } from "../api";
import { useTopBarActions } from "../context/TopBarActionsContext";
import { usePageTracking } from "../hooks/usePageTracking";
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
const END_PHASE_DELAY_MS = 20000;
const END_DIALOG_MESSAGE = "对话结束，您可以点击顶部导航栏中间的「下一页」继续";

export default function ChatPage() {
  const navigate = useNavigate();
  const { setTopBarAction } = useTopBarActions();
  const chatWindowRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const endPhaseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [isAnger, setIsAnger] = useState(false);
  const [aiRoundCount, setAiRoundCount] = useState(0);
  const [maxRounds, setMaxRounds] = useState(6);
  const [chatFinished, setChatFinished] = useState(false);
  const [endPhaseReady, setEndPhaseReady] = useState(false);
  const [showEndDialog, setShowEndDialog] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [latestAnimatedKey, setLatestAnimatedKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  usePageTracking("chat");

  const handleGoToSurvey = useCallback(async () => {
    await navigate("/survey");
  }, [navigate]);

  const activateEndPhase = useCallback(() => {
    setEndPhaseReady(true);
    setShowEndDialog(true);
  }, []);

  const scheduleEndPhase = useCallback(() => {
    if (endPhaseTimerRef.current) {
      clearTimeout(endPhaseTimerRef.current);
    }
    endPhaseTimerRef.current = setTimeout(() => {
      activateEndPhase();
      endPhaseTimerRef.current = null;
    }, END_PHASE_DELAY_MS);
  }, [activateEndPhase]);

  useEffect(() => {
    return () => {
      if (endPhaseTimerRef.current) {
        clearTimeout(endPhaseTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!endPhaseReady) {
      setTopBarAction(null);
      return;
    }

    setTopBarAction(
      <button type="button" className="btn-pill btn-pill-nav" onClick={() => void handleGoToSurvey()}>
        下一页
      </button>
    );

    return () => setTopBarAction(null);
  }, [endPhaseReady, handleGoToSurvey, setTopBarAction]);

  useEffect(() => {
    const session = loadSession();
    if (!session) return;

    void Promise.all([api.getConfig(), api.getChatHistory(session.session_token)])
      .then(([config, history]) => {
        setMaxRounds(config.max_ai_rounds);
        setIsAnger(history.is_anger);
        setAiRoundCount(history.ai_round_count);
        setChatFinished(history.chat_finished);
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
        if (history.chat_finished) {
          activateEndPhase();
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [activateEndPhase]);

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

          if (payload.chat_finished) {
            scheduleEndPhase();
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

      {showEndDialog && (
        <div
          className="modal-backdrop"
          onClick={() => setShowEndDialog(false)}
          role="presentation"
        >
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="chat-end-dialog-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="modal-close-btn"
              aria-label="关闭"
              onClick={() => setShowEndDialog(false)}
            >
              ×
            </button>
            <h2 id="chat-end-dialog-title" className="modal-title">
              {END_DIALOG_MESSAGE}
            </h2>
          </div>
        </div>
      )}
    </>
  );
}
