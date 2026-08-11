import { useState } from "react";
import { ClipboardList } from "lucide-react";
import { useApp } from "../context/AppContext";
import { TOPICS } from "../data/navigation";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";

export function AIExamsPage() {
  const { subject, board } = useApp();
  const [duration, setDuration] = useState("60 min");
  const [difficulty, setDifficulty] = useState("Balanced");
  const [includeBank, setIncludeBank] = useState(true);
  const [topics, setTopics] = useState(["Cell Biology", "Genetics", "Ecology"]);

  const toggle = (t: string) =>
    setTopics((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));

  return (
    <div className="page">
      <div className="page__eyebrow">AI-curated exams</div>
      <h1 className="page__title">Fully customisable papers</h1>
      <p className="page__desc">
        Generate exams from PYQs plus additional bank questions. Tune difficulty and
        topics for {board} {subject}.
      </p>

      <div className="grid-2" style={{ marginTop: 24, alignItems: "start" }}>
        <div className="panel">
          <div className="panel__title">Exam blueprint</div>
          <div className="form-grid">
            <div className="field">
              <label>Duration</label>
              <div className="chip-row">
                {["30 min", "60 min", "90 min", "2 hrs"].map((d) => (
                  <Chip key={d} active={duration === d} onClick={() => setDuration(d)}>
                    {d}
                  </Chip>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Difficulty</label>
              <div className="chip-row">
                {["Foundation", "Balanced", "A* stretch"].map((d) => (
                  <Chip key={d} active={difficulty === d} onClick={() => setDifficulty(d)}>
                    {d}
                  </Chip>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Topics</label>
              <div className="chip-row">
                {TOPICS.slice(0, 8).map((t) => (
                  <Chip key={t} active={topics.includes(t)} onClick={() => toggle(t)}>
                    {t}
                  </Chip>
                ))}
              </div>
            </div>
            <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14 }}>
              <input
                type="checkbox"
                checked={includeBank}
                onChange={(e) => setIncludeBank(e.target.checked)}
              />
              Include additional question-bank items beyond PYQs
            </label>
            <Button size="lg" leftIcon={<ClipboardList size={16} />}>
              Generate exam
            </Button>
          </div>
        </div>

        <div className="panel">
          <div className="panel__title">Preview structure</div>
          <div className="panel__sub">Based on your current settings</div>
          <div className="lesson-list" style={{ marginTop: 16 }}>
            {[
              { title: "Section A — Short answers", meta: "8 questions · 20 marks" },
              { title: "Section B — Structured", meta: "4 questions · 28 marks" },
              { title: "Section C — Extended", meta: "1 question · 12 marks" },
            ].map((s, i) => (
              <div key={s.title} className={`lesson-card ${i === 0 ? "lesson-card--active" : ""}`}>
                {i === 0 && <div className="lesson-card__start">Live</div>}
                <div className="lesson-card__icon">
                  <span style={{ fontWeight: 800, fontSize: 12 }}>{String.fromCharCode(65 + i)}</span>
                </div>
                <div className="lesson-card__body">
                  <div className="lesson-card__title">{s.title}</div>
                  <div className="lesson-card__meta">{s.meta}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, fontSize: 13, color: "var(--color-text-secondary)" }}>
            Source mix: {includeBank ? "70% PYQ · 30% bank" : "100% PYQ"} · {difficulty} · {duration}
          </div>
        </div>
      </div>
    </div>
  );
}
