import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getMarkerLabel,
  type ExamBoard,
  type Subject,
} from "../data/navigation";

type AppContextValue = {
  subject: Subject;
  board: ExamBoard;
  setSubject: (s: Subject) => void;
  setBoard: (b: ExamBoard) => void;
  markerLabel: string;
  streak: number;
  points: number;
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [subject, setSubject] = useState<Subject>("Biology");
  const [board, setBoard] = useState<ExamBoard>("OCR");

  const value = useMemo(
    () => ({
      subject,
      board,
      setSubject,
      setBoard,
      markerLabel: getMarkerLabel(subject),
      streak: 12,
      points: 1840,
    }),
    [subject, board],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
