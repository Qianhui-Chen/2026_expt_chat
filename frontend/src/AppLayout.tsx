import { useEffect, useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { loadSession, type SessionState } from "./api";
import { TopBarActionsContext } from "./context/TopBarActionsContext";
import "./styles.css";

/** 分组 UI 页：导航栏跟随奇偶配色（instruction 无导航栏） */
const GROUPED_NAV_PATHS = new Set(["/meet", "/chat"]);

export default function AppLayout() {
  const location = useLocation();
  const isInstruction = location.pathname === "/instruction";
  const isMeet = location.pathname === "/meet";
  const isPublicEntry = isInstruction || isMeet;
  const [session, setSession] = useState<SessionState | null>(() => loadSession());
  const [topBarAction, setTopBarAction] = useState<ReactNode>(null);

  useEffect(() => {
    const syncSession = () => setSession(loadSession());
    syncSession();
    window.addEventListener("anger-session-updated", syncSession);
    window.addEventListener("storage", syncSession);
    return () => {
      window.removeEventListener("anger-session-updated", syncSession);
      window.removeEventListener("storage", syncSession);
    };
  }, [location.pathname]);

  useEffect(() => {
    const shell = document.querySelector(".app-shell");
    if (!shell) return;

    shell.classList.remove("meet-theme-tool", "meet-theme-companion");
    if (session && GROUPED_NAV_PATHS.has(location.pathname)) {
      shell.classList.add(
        session.bot_type === "companion" ? "meet-theme-companion" : "meet-theme-tool"
      );
    }

    return () => {
      shell.classList.remove("meet-theme-tool", "meet-theme-companion");
    };
  }, [session, location.pathname]);

  // Instruction：无导航栏；Meet / Chat / 有 session 的其它页显示
  const showTopBar = !isInstruction && (isMeet || Boolean(session));

  if (!session && !isPublicEntry) {
    return <Navigate to="/instruction" replace />;
  }

  return (
    <TopBarActionsContext.Provider value={{ setTopBarAction }}>
      <div className={`app-shell${isInstruction ? " app-shell--no-top-bar" : ""}`}>
        {showTopBar && (
          <header className="top-bar">
            <div className="top-bar-start">
              {session?.completion_code ? (
                <div className="user-id-badge">ID：{session.completion_code}</div>
              ) : null}
            </div>
            <div className="top-bar-center">{topBarAction}</div>
            <div className="top-bar-end" aria-hidden="true" />
          </header>
        )}
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </TopBarActionsContext.Provider>
  );
}
