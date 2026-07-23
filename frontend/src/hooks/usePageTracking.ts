import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { api, loadSession } from "../api";

export function usePageTracking(pageName: string) {
  const location = useLocation();
  const enteredAtRef = useRef(new Date().toISOString());

  useEffect(() => {
    enteredAtRef.current = new Date().toISOString();
    const session = loadSession();
    if (!session) return;

    return () => {
      void api
        .logPageLeave(
          session.session_token,
          pageName,
          enteredAtRef.current,
          new Date().toISOString()
        )
        .catch(() => {
          /* 埋点失败不打断实验流程 */
        });
    };
  }, [location.pathname, pageName]);
}

export async function trackClick(page: string, element: string) {
  const session = loadSession();
  if (!session) return;
  try {
    await api.logClick(session.session_token, page, element);
  } catch {
    /* 埋点失败不打断实验流程 */
  }
}
