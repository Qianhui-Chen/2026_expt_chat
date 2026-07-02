import { useNavigate } from "react-router-dom";

import { CONSENT_SURVEY_URL } from "../config";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";

export default function ConsentPage() {
  const navigate = useNavigate();
  usePageTracking("consent");

  const handleNext = async () => {
    await trackClick("consent", "next");
    navigate("/instruction");
  };

  return (
    <section className="flow-page">
      <div className="flow-body consent-body">
        <div className="consent-copy">
  <p>
    请阅读并完成知情同意书（知情同意书加载需要 3 秒左右）。请确保点击蓝色“提交”按钮后，再点击“下一页”。
  </p>
        </div>
        <div className="survey-slot">
          {CONSENT_SURVEY_URL ? (
            <iframe title="知情同意问卷" src={CONSENT_SURVEY_URL} className="survey-frame" />
          ) : (
            <div className="survey-placeholder">知情同意问卷占位区</div>
          )}
        </div>
      </div>
      <div className="flow-footer">
        <button className="btn-pill" onClick={handleNext}>
          下一页
        </button>
      </div>
    </section>
  );
}
