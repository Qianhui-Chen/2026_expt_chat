import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, saveSession } from "../api";
import { trackClick, usePageTracking } from "../hooks/usePageTracking";

export default function LoginPage() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  usePageTracking("login");

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await api.login(userId.trim());
      saveSession(result);
      await trackClick("login", "submit");
      navigate("/consent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="login-page">
      <div className="login-stack">
        <h1 className="login-welcome">Welcome!</h1>
        <p className="login-title">请输入你的实验ID</p>
        <p className="login-hint">实验ID由字母和数字组成</p>
        <form onSubmit={handleSubmit} className="login-form">
          <input
            id="userId"
            className="login-input"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder=""
            autoComplete="off"
            aria-label="实验ID"
          />
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="btn-primary btn-login" disabled={loading || !userId.trim()}>
            {loading ? "验证中..." : "登录"}
          </button>
        </form>
      </div>
    </section>
  );
}
