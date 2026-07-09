import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./AppLayout";
import InstructionPage from "./pages/InstructionPage";
import ChatPage from "./pages/ChatPage";
import SurveyPage from "./pages/SurveyPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/instruction" element={<InstructionPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/survey" element={<SurveyPage />} />
          <Route path="*" element={<Navigate to="/instruction" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
