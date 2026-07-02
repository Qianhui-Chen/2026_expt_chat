import { createContext, useContext, type ReactNode } from "react";

type TopBarActionsContextValue = {
  setTopBarAction: (action: ReactNode) => void;
};

export const TopBarActionsContext = createContext<TopBarActionsContextValue | null>(null);

export function useTopBarActions() {
  const context = useContext(TopBarActionsContext);
  if (!context) {
    throw new Error("useTopBarActions must be used within AppLayout");
  }
  return context;
}
