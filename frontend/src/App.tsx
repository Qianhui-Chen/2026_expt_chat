import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./AppLayout";
import InstructionPage from "./pages/InstructionPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/instruction" element={<InstructionPage />} />
          <Route path="/meet" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/instruction" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
