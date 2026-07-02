import { useState } from "react";

import { api, loadSession } from "../api";
import { POST_SURVEY_URL } from "../config";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";

export default function SurveyPage() {
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  usePageTracking("survey");

  const handleSubmit = async () => {
    const session = loadSession();
    if (!session) return;

    setSubmitting(true);
    setError("");
    try {
      await api.completeExperiment(session.session_token);
      await trackClick("survey", "submit");
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <section className="flow-page survey-page">
        <div className="flow-body survey-body">
          <div className="survey-slot">
            {POST_SURVEY_URL ? (
              <iframe title="后测问卷" src={POST_SURVEY_URL} className="survey-frame" />
            ) : (
              <div className="survey-placeholder">后测问卷链接占位区</div>
            )}
          </div>
        </div>
        {error && <p className="error-text survey-error">{error}</p>}
        <div className="flow-footer">
          <button className="btn-pill" onClick={() => void handleSubmit()} disabled={submitting}>
            {submitting ? "提交中..." : "提交"}
          </button>
        </div>
      </section>

      {submitted && (
        <div className="modal-backdrop">
          <div className="modal-card completion-card">
            <h2 className="modal-title">实验完成</h2>
            <p className="modal-subtitle">
              感谢您的参与！如需再次参与，请返回登录页并使用相同实验 ID 重新登录。
            </p>
          </div>
        </div>
      )}
    </>
  );
}
