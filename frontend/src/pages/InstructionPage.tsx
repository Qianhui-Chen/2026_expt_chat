import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, clearSession, loadSession } from "../api";
import {
  INSTRUCTION_PARAGRAPHS,
  INSTRUCTION_SCREENING_NO,
  INSTRUCTION_SCREENING_QUESTION,
  INSTRUCTION_SCREENING_YES,
  INSTRUCTION_SCREENOUT_MESSAGE,
  INSTRUCTION_SCREENOUT_TITLE,
  INSTRUCTION_TITLE,
} from "../content/instruction";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";

type ScreeningChoice = "yes" | "no";

export default function InstructionPage() {
  const navigate = useNavigate();
  const [choice, setChoice] = useState<ScreeningChoice | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [showScreenout, setShowScreenout] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  usePageTracking("instruction");

  useEffect(() => {
    const session = loadSession();
    if (!session) {
      setCheckingSession(false);
      return;
    }

    void api
      .getSession(session.session_token)
      .then((data) => {
        if (data.has_similar_experience === true) {
          navigate("/chat", { replace: true });
          return;
        }
        if (data.has_similar_experience === false) {
          clearSession();
          setShowScreenout(true);
        }
      })
      .catch(() => {
        // 会话查询失败时仍允许用户继续作答
      })
      .finally(() => setCheckingSession(false));
  }, [navigate]);
  const handleContinue = async () => {
    if (!choice) return;

    const session = loadSession();
    if (!session) {
      navigate("/login", { replace: true });
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const hasExperience = choice === "yes";
      await trackClick(
        "instruction",
        hasExperience ? "has_experience_yes" : "has_experience_no"
      );
      const result = await api.submitInstructionScreening(
        session.session_token,
        hasExperience
      );

      if (result.continue_experiment) {
        await trackClick("instruction", "next");
        navigate("/chat");
        return;
      }

      clearSession();
      setShowScreenout(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDismissScreenout = () => {
    navigate("/login", { replace: true });
  };

  return (
    <>
      <section className="flow-page">
        {checkingSession ? (
          <div className="instruction-loading">加载中...</div>
        ) : (
          <>
        <div className="flow-body instruction-body">
          <div className="instruction-illustration">
            <img
              src="/assets/instruction-illustration.png"
              alt="实验情境插图"
              className="instruction-image"
            />
          </div>
          <aside className="scenario-panel">
            <h2 className="scenario-title">{INSTRUCTION_TITLE}</h2>
            {INSTRUCTION_PARAGRAPHS.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
            <fieldset className="screening-fieldset">
              <legend className="screening-question">{INSTRUCTION_SCREENING_QUESTION}</legend>
              <div className="screening-options">
                <label className="screening-option">
                  <input
                    type="radio"
                    name="similar-experience"
                    value="yes"
                    checked={choice === "yes"}
                    onChange={() => setChoice("yes")}
                  />
                  <span>{INSTRUCTION_SCREENING_YES}</span>
                </label>
                <label className="screening-option">
                  <input
                    type="radio"
                    name="similar-experience"
                    value="no"
                    checked={choice === "no"}
                    onChange={() => setChoice("no")}
                  />
                  <span>{INSTRUCTION_SCREENING_NO}</span>
                </label>
              </div>
            </fieldset>
          </aside>
        </div>
        {error && <p className="error-text instruction-error">{error}</p>}
        <div className="flow-footer">
          <button
            className="btn-pill"
            onClick={() => void handleContinue()}
            disabled={!choice || submitting}
          >
            {submitting ? "提交中..." : "下一步"}
          </button>
        </div>
          </>
        )}
      </section>

      {showScreenout && (
        <div className="modal-backdrop">
          <div className="modal-card completion-card">
            <h2 className="modal-title">{INSTRUCTION_SCREENOUT_TITLE}</h2>
            <p className="modal-subtitle">{INSTRUCTION_SCREENOUT_MESSAGE}</p>
            <button className="btn-pill" onClick={handleDismissScreenout}>
              返回登录页
            </button>
          </div>
        </div>
      )}
    </>
  );
}
