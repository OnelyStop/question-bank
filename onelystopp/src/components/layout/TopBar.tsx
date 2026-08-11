import {
  Bell,
  Hexagon,
  Search,
  Zap,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import type { ExamBoard, Subject } from "../../data/navigation";
import { Button } from "../ui/Button";
import "./TopBar.css";

const SUBJECTS: Subject[] = [
  "Biology",
  "Chemistry",
  "Physics",
  "Economics",
  "History",
  "English Literature",
  "Maths",
];

const BOARDS: ExamBoard[] = ["OCR", "AQA", "Edexcel", "CIE"];

export function TopBar() {
  const { subject, board, setSubject, setBoard, streak, points } = useApp();

  return (
    <header className="topbar">
      <div className="topbar__banner">
        <span>
          Instant feedback using exact <strong>{board}</strong> marking criteria
          · trained on 2017–2025 papers & specs
        </span>
      </div>

      <div className="topbar__row">
        <div className="topbar__search">
          <Search size={16} strokeWidth={1.75} />
          <input
            type="search"
            placeholder="Search topics, past papers, notes…"
            aria-label="Search"
          />
          <kbd className="topbar__kbd">⌘K</kbd>
        </div>

        <div className="topbar__controls">
          <label className="topbar__select">
            <span className="sr-only">Subject</span>
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value as Subject)}
            >
              {SUBJECTS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <label className="topbar__select topbar__select--board">
            <span className="sr-only">Exam board</span>
            <select
              value={board}
              onChange={(e) => setBoard(e.target.value as ExamBoard)}
            >
              {BOARDS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </label>

          <div className="topbar__stat" title="Streak">
            <Zap size={15} strokeWidth={2} />
            <span>{streak}</span>
          </div>
          <div className="topbar__stat" title="Points">
            <Hexagon size={15} strokeWidth={2} />
            <span>{points}</span>
          </div>

          <button type="button" className="topbar__icon-btn" aria-label="Notifications">
            <Bell size={17} strokeWidth={1.75} />
            <span className="topbar__dot" />
          </button>

          <Button size="sm">Upgrade</Button>

          <div className="topbar__avatar" aria-label="Profile">
            A
          </div>
        </div>
      </div>
    </header>
  );
}
