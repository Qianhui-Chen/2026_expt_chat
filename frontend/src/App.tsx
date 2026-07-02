import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./AppLayout";
import LoginPage from "./pages/LoginPage";
import ConsentPage from "./pages/ConsentPage";
import InstructionPage from "./pages/InstructionPage";
import ChatPage from "./pages/ChatPage";
import SurveyPage from "./pages/SurveyPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/consent" element={<ConsentPage />} />
          <Route path="/instruction" element={<InstructionPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/survey" element={<SurveyPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
