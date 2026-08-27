import { useEffect, useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { loadSession, type SessionState } from "./api";
import { TopBarActionsContext } from "./context/TopBarActionsContext";
import "./styles.css";

export default function AppLayout() {
  const location = useLocation();
  const isInstruction = location.pathname === "/instruction";
  const isPublicEntry = isInstruction;
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

  // Instruction：无导航栏；有 session 的其它页显示
  const showTopBar = !isInstruction && Boolean(session);

  if (!session && !isPublicEntry) {
    return <Navigate to="/instruction" replace />;
  }

  return (
    <TopBarActionsContext.Provider value={{ setTopBarAction }}>
      <div className={`app-shell${isInstruction ? " app-shell--no-top-bar" : ""}`}>
        {showTopBar && (
          <header className="top-bar">
            <div className="top-bar-start" aria-hidden="true" />
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
