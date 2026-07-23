import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { ensureActiveSession, loadSession, type SessionState } from "../api";
import { INSTRUCTION_COPY, INSTRUCTION_CTA_LABEL } from "../content/instruction";
import { splitBoldSegments } from "../content/meet";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";

const INSTRUCTION_COUNTDOWN_SEC = 5;

function RichParagraph({ text }: { text: string }) {
  const nodes: ReactNode[] = splitBoldSegments(text).map((segment, index) =>
    segment.bold ? <strong key={index}>{segment.text}</strong> : <span key={index}>{segment.text}</span>
  );
  return <p>{nodes}</p>;
}

export default function InstructionPage() {
  const navigate = useNavigate();
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [countdown, setCountdown] = useState(INSTRUCTION_COUNTDOWN_SEC);
  const [navigating, setNavigating] = useState(false);
  const [session, setSession] = useState<SessionState | null>(() => loadSession());
  const [bootstrapError, setBootstrapError] = useState("");
  usePageTracking("instruction");

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

  useEffect(() => {
    if (!session) return;

    setCountdown(INSTRUCTION_COUNTDOWN_SEC);
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
  }, [session]);

  const handleContinue = useCallback(async () => {
    if (!session || countdown !== 0 || navigating) return;

    setNavigating(true);
    try {
      await trackClick("instruction", "meet-intro");
      navigate("/meet");
    } finally {
      setNavigating(false);
    }
  }, [session, countdown, navigating, navigate]);

  if (!session && !bootstrapError) {
    return (
      <section className="flow-page instruction-page">
        <div className="instruction-loading">正在准备实验...</div>
      </section>
    );
  }

  const ready = Boolean(session) && countdown === 0 && !navigating;
  const ctaLabel = navigating
    ? "跳转中..."
    : countdown > 0
      ? `${INSTRUCTION_CTA_LABEL} (${countdown})`
      : INSTRUCTION_CTA_LABEL;

  return (
    <section className="flow-page instruction-page">
      <div className="flow-body instruction-body">
        <h1 className="instruction-welcome">Welcome!</h1>
        <div className="scenario-panel">
          <h2 className="scenario-title">{INSTRUCTION_COPY.title}</h2>
          {INSTRUCTION_COPY.paragraphs.map((paragraph, index) => (
            <RichParagraph key={index} text={paragraph} />
          ))}
        </div>
        <div className="instruction-cta-wrap">
          <button
            type="button"
            className={`btn-pill btn-pill-next-step instruction-cta${ready ? " btn-pill-next-step-ready" : ""}`}
            onClick={() => void handleContinue()}
            disabled={!ready}
          >
            {ctaLabel}
          </button>
        </div>
      </div>
      {bootstrapError && !session && (
        <p className="error-text instruction-error">{bootstrapError}</p>
      )}
    </section>
  );
}
