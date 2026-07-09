import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ensureActiveSession } from "../api";
import { INSTRUCTION_PARAGRAPHS, INSTRUCTION_TITLE } from "../content/instruction";
import { useTopBarActions } from "../context/TopBarActionsContext";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";

const INSTRUCTION_COUNTDOWN_SEC = 10;

export default function InstructionPage() {
  const navigate = useNavigate();
  const { setTopBarAction } = useTopBarActions();
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [countdown, setCountdown] = useState(INSTRUCTION_COUNTDOWN_SEC);
  const [navigating, setNavigating] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [bootstrapError, setBootstrapError] = useState("");
  usePageTracking("instruction");

  useEffect(() => {
    let cancelled = false;

    void ensureActiveSession()
      .then(() => {
        if (cancelled) return;
        setSessionReady(true);
        setBootstrapError("");
      })
      .catch((err) => {
        if (cancelled) return;
        setBootstrapError(err instanceof Error ? err.message : "无法开始实验");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
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
  }, []);

  const handleContinue = useCallback(async () => {
    if (countdown !== 0 || navigating || !sessionReady) return;

    setNavigating(true);
    try {
      await trackClick("instruction", "next");
      navigate("/chat");
    } finally {
      setNavigating(false);
    }
  }, [countdown, navigating, sessionReady, navigate]);

  useEffect(() => {
    if (!sessionReady) {
      setTopBarAction(null);
      return;
    }

    const ready = countdown === 0 && !navigating;
    const label =
      navigating ? "跳转中..." : countdown > 0 ? `下一步 (${countdown})` : "下一步";

    setTopBarAction(
      <button
        type="button"
        className={`btn-pill btn-pill-next-step${ready ? " btn-pill-next-step-ready" : ""}`}
        onClick={() => void handleContinue()}
        disabled={!ready}
      >
        {label}
      </button>
    );

    return () => setTopBarAction(null);
  }, [sessionReady, countdown, navigating, handleContinue, setTopBarAction]);

  if (!sessionReady && !bootstrapError) {
    return (
      <section className="flow-page">
        <div className="instruction-loading">正在准备实验...</div>
      </section>
    );
  }

  return (
    <section className="flow-page">
      <div className="flow-body instruction-body">
        <div className="scenario-panel">
          <h2 className="scenario-title">{INSTRUCTION_TITLE}</h2>
          {INSTRUCTION_PARAGRAPHS.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      </div>
      {bootstrapError && <p className="error-text instruction-error">{bootstrapError}</p>}
    </section>
  );
}
