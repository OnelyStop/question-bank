import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { AIExamsPage } from "./pages/AIExamsPage";
import { DiagramPage } from "./pages/DiagramPage";
import { HomePage } from "./pages/HomePage";
import { InterviewPage } from "./pages/InterviewPage";
import { MarkerPage } from "./pages/MarkerPage";
import { MemoryPage } from "./pages/MemoryPage";
import { PastPapersPage } from "./pages/PastPapersPage";
import { ProgressPage } from "./pages/ProgressPage";
import { PYQMixPage } from "./pages/PYQMixPage";
import { QuestionBankPage } from "./pages/QuestionBankPage";
import { RevisionPage } from "./pages/RevisionPage";
import { StickyNotesPage } from "./pages/StickyNotesPage";
import { TheoryPage } from "./pages/TheoryPage";
import { TutorPage } from "./pages/TutorPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="question-bank" element={<QuestionBankPage />} />
        <Route path="past-papers" element={<PastPapersPage />} />
        <Route path="pyq-mix" element={<PYQMixPage />} />
        <Route path="ai-exams" element={<AIExamsPage />} />
        <Route path="theory" element={<TheoryPage />} />
        <Route path="revision" element={<RevisionPage />} />
        <Route path="marker" element={<MarkerPage />} />
        <Route path="diagrams" element={<DiagramPage />} />
        <Route path="interview" element={<InterviewPage />} />
        <Route path="tutor" element={<TutorPage />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="notes" element={<StickyNotesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
