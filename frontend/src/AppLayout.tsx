import { useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { loadSession } from "./api";
import { TopBarActionsContext } from "./context/TopBarActionsContext";
import "./styles.css";

export default function AppLayout() {
  const session = loadSession();
  const location = useLocation();
  const isInstruction = location.pathname === "/instruction";
  const showTopBar = isInstruction || Boolean(session);
  const [topBarAction, setTopBarAction] = useState<ReactNode>(null);

  if (!session && !isInstruction) {
    return <Navigate to="/instruction" replace />;
  }

  return (
    <TopBarActionsContext.Provider value={{ setTopBarAction }}>
      <div className="app-shell">
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
