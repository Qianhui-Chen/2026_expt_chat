import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { ensureActiveSession, loadSession, type SessionState } from "../api";
import {
  MEET_CLICK_CARD_HINT,
  MEET_COMPANION_CARD_IMAGE,
  MEET_COMPANION_CARD_LABEL,
  MEET_EXPANDED_CARD_COUNT,
  MEET_FAN_CARD_COUNT,
  MEET_TOOL_CARD_IMAGE,
  MEET_TOOL_CARD_LABEL,
  getMeetExpandedCopy,
  splitBoldSegments,
} from "../content/meet";
import { useTopBarActions } from "../context/TopBarActionsContext";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";

const MEET_COUNTDOWN_SEC = 8;

function RichLine({ text, className }: { text: string; className?: string }) {
  const nodes: ReactNode[] = splitBoldSegments(text).map((segment, index) =>
    segment.bold ? <strong key={index}>{segment.text}</strong> : <span key={index}>{segment.text}</span>
  );
  return <p className={className}>{nodes}</p>;
}

export default function MeetYourBotPage() {
  const navigate = useNavigate();
  const { setTopBarAction } = useTopBarActions();
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [countdown, setCountdown] = useState(MEET_COUNTDOWN_SEC);
  const [navigating, setNavigating] = useState(false);
  const [session, setSession] = useState<SessionState | null>(() => loadSession());
  const [bootstrapError, setBootstrapError] = useState("");
  const [fanOpen, setFanOpen] = useState(false);
  const [cardsReady, setCardsReady] = useState(false);
  const [expanded, setExpanded] = useState(false);
  usePageTracking("meet");

  const isCompanion = session?.bot_type === "companion";
  const cardLabel = isCompanion ? MEET_COMPANION_CARD_LABEL : MEET_TOOL_CARD_LABEL;
  const cardImage = isCompanion ? MEET_COMPANION_CARD_IMAGE : MEET_TOOL_CARD_IMAGE;
  const stackVariant = isCompanion ? "companion" : "tool";
  const expandedCopy = getMeetExpandedCopy(isCompanion ? "companion" : "tool");
  const cardCount = expanded ? MEET_EXPANDED_CARD_COUNT : MEET_FAN_CARD_COUNT;

  useEffect(() => {
    let cancelled = false;

    void ensureActiveSession()
      .then((active) => {
        if (cancelled) return;
        setSession(active);
        setBootstrapError("");
      })
      .catch((err) => {
        if (cancelled) return;
        const local = loadSession();
        if (local) {
          setSession(local);
          setBootstrapError("");
          return;
        }
        setBootstrapError(err instanceof Error ? err.message : "无法开始实验");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // 进入 Meet 即从扇形卡牌开始（原第二步），自动展开
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => setFanOpen(true), 80);
    return () => window.clearTimeout(timer);
  }, [session]);

  useEffect(() => {
    if (!expanded) {
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
      setCountdown(MEET_COUNTDOWN_SEC);
      return;
    }

    setCountdown(MEET_COUNTDOWN_SEC);
    countdownTimerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
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
  }, [expanded]);

  const handleContinue = useCallback(async () => {
    if (!expanded || countdown !== 0 || navigating || !session) return;

    setNavigating(true);
    try {
      await trackClick("meet", "next");
      navigate("/chat");
    } finally {
      setNavigating(false);
    }
  }, [expanded, countdown, navigating, session, navigate]);

  useEffect(() => {
    if (!session) {
      setTopBarAction(null);
      return () => setTopBarAction(null);
    }

    // 扇形卡牌阶段：导航栏提示点击卡片
    if (!expanded) {
      setTopBarAction(
        <p className="meet-top-hint">{MEET_CLICK_CARD_HINT}</p>
      );
      return () => setTopBarAction(null);
    }

    const ready = countdown === 0 && !navigating;
    const label =
      navigating ? "跳转中..." : countdown > 0 ? `下一步 (${countdown})` : "下一步";
    const toneClass = isCompanion ? "meet-next-btn--companion" : "meet-next-btn--tool";

    setTopBarAction(
      <button
        type="button"
        className={`btn-pill meet-next-btn ${toneClass}${ready ? " meet-next-btn--ready" : ""}`}
        onClick={() => void handleContinue()}
        disabled={!ready}
      >
        {label}
      </button>
    );

    return () => setTopBarAction(null);
  }, [
    session,
    expanded,
    countdown,
    navigating,
    isCompanion,
    handleContinue,
    setTopBarAction,
  ]);

  useEffect(() => {
    if (!fanOpen || expanded) return;
    const timer = window.setTimeout(() => setCardsReady(true), 1100);
    return () => window.clearTimeout(timer);
  }, [fanOpen, expanded]);

  const handleFrontCardClick = useCallback(() => {
    if (!cardsReady || expanded) return;
    void trackClick("meet", "front-card");
    setCardsReady(false);
    setExpanded(true);
  }, [cardsReady, expanded]);

  if (!session && !bootstrapError) {
    return (
      <section className="flow-page meet-page">
        <div className="instruction-loading">正在准备实验...</div>
      </section>
    );
  }

  const stackClass = [
    "meet-card-stack",
    `meet-card-stack--${stackVariant}`,
    fanOpen ? "meet-card-stack--open" : "",
    cardsReady && !expanded ? "meet-card-stack--pulse" : "",
    expanded ? "meet-card-stack--expanded" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className="flow-page meet-page">
      <div className="flow-body meet-body">
        <div className="meet-stage">
          <div className={stackClass} aria-label={cardLabel}>
            {Array.from({ length: cardCount }, (_, index) => {
              const isFront = index === 0;
              const isBottom = index >= 1;
              const layer = cardCount - index;
              const panel = isBottom && expanded ? expandedCopy.panels[index - 1] : null;

              return (
                <article
                  key={index}
                  className={`meet-card meet-card--${index}${isFront ? " meet-card--front" : " meet-card--back"}`}
                  style={
                    {
                      "--card-i": index,
                      "--card-layer": layer,
                    } as CSSProperties
                  }
                  {...(isFront && !expanded
                    ? {
                        role: "button",
                        tabIndex: cardsReady ? 0 : -1,
                        "aria-disabled": !cardsReady,
                        onClick: handleFrontCardClick,
                        onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
                          if (!cardsReady || expanded) return;
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            handleFrontCardClick();
                          }
                        },
                      }
                    : {})}
                >
                  {isFront && (
                    <>
                      <div className="meet-card-face meet-card-face--intro">
                        <div className="meet-card-media">
                          <img
                            className="meet-card-image"
                            src={cardImage}
                            alt=""
                            onError={(event) => {
                              event.currentTarget.style.display = "none";
                            }}
                          />
                        </div>
                        <span className="meet-card-label">{cardLabel}</span>
                      </div>
                      <div className="meet-card-face meet-card-face--hero">
                        <div className="meet-card-media">
                          <img
                            className="meet-card-image"
                            src={cardImage}
                            alt=""
                            onError={(event) => {
                              event.currentTarget.style.display = "none";
                            }}
                          />
                        </div>
                        <div className="meet-hero-copy">
                          {expandedCopy.heroLines.map((line, lineIndex) => (
                            <RichLine key={lineIndex} text={line} className="meet-hero-line" />
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                  {panel && (
                    <div className="meet-card-face meet-card-face--panel">
                      <div className="meet-panel-box">
                        <h3 className="meet-panel-title">{panel.title || "\u00A0"}</h3>
                        <div className="meet-panel-body">
                          {panel.lines.map((line, lineIndex) => (
                            <RichLine key={lineIndex} text={line} className="meet-detail-line" />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
            {expanded && (
              <div className="meet-mid-copy" aria-hidden={expandedCopy.midLines.length === 0}>
                {expandedCopy.midLines.map((line, lineIndex) => (
                  <RichLine key={lineIndex} text={line} className="meet-mid-line" />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      {bootstrapError && !session && (
        <p className="error-text instruction-error">{bootstrapError}</p>
      )}
    </section>
  );
}
