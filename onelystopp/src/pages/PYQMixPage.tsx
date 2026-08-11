import { useState } from "react";
import { Sparkles } from "lucide-react";
import { useApp } from "../context/AppContext";
import { TOPICS } from "../data/navigation";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";

export function PYQMixPage() {
  const { subject, board } = useApp();
  const [yearFrom, setYearFrom] = useState("2019");
  const [yearTo, setYearTo] = useState("2025");
  const [difficulty, setDifficulty] = useState("Exam mix");
  const [selected, setSelected] = useState<string[]>(["Cell Biology", "Genetics"]);
  const [generated, setGenerated] = useState(false);

  const toggle = (topic: string) => {
    setSelected((prev) =>
      prev.includes(topic) ? prev.filter((t) => t !== topic) : [...prev, topic],
    );
  };

  return (
    <div className="page page--split">
      <div>
        <div className="page__eyebrow">PYQ mix generator</div>
        <h1 className="page__title">Build a set that mirrors exam trends</h1>
        <p className="page__desc">
          Choose year range, difficulty, and topics. We’ll assemble a customised PYQ pack
          for {board} {subject} that reflects how recent papers actually look.
        </p>

        <div className="panel" style={{ marginTop: 24 }}>
          <div className="panel__title">Mix controls</div>
          <div className="form-grid">
            <div className="grid-2">
              <div className="field">
                <label>From year</label>
                <select value={yearFrom} onChange={(e) => setYearFrom(e.target.value)}>
                  {["2017", "2018", "2019", "2020", "2021", "2022"].map((y) => (
                    <option key={y}>{y}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>To year</label>
                <select value={yearTo} onChange={(e) => setYearTo(e.target.value)}>
                  {["2022", "2023", "2024", "2025"].map((y) => (
                    <option key={y}>{y}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field">
              <label>Difficulty profile</label>
              <div className="chip-row">
                {["Mostly easy", "Exam mix", "Stretch / hard"].map((d) => (
                  <Chip key={d} active={difficulty === d} onClick={() => setDifficulty(d)}>
                    {d}
                  </Chip>
                ))}
              </div>
            </div>

            <div className="field">
              <label>Topics to cover</label>
              <div className="chip-row">
                {TOPICS.map((t) => (
                  <Chip key={t} active={selected.includes(t)} onClick={() => toggle(t)}>
                    {t}
                  </Chip>
                ))}
              </div>
            </div>

            <Button
              size="lg"
              leftIcon={<Sparkles size={16} />}
              onClick={() => setGenerated(true)}
            >
              Generate PYQ mix
            </Button>
          </div>
        </div>

        {generated && (
          <div className="section-block">
            <div className="section-block__label">Your mix</div>
            <div className="section-block__title">
              {selected.length || 1} topics · {yearFrom}–{yearTo} · {difficulty}
            </div>
            <div className="lesson-list" style={{ marginTop: 14 }}>
              {[
                "2024 Paper 1 Q3 — data analysis",
                "2022 Paper 2 Q5 — extended response",
                "2025 Specimen Q2 — short structured",
                "2021 Paper 1 Q7 — calculation",
                "2023 Paper 2 Q1 — definitions",
              ].map((title, i) => (
                <div key={title} className={`lesson-card ${i === 0 ? "lesson-card--active" : ""}`}>
                  {i === 0 && <div className="lesson-card__start">Start</div>}
                  <div className="lesson-card__icon">
                    <span style={{ fontSize: 12, fontWeight: 800 }}>{i + 1}</span>
                  </div>
                  <div className="lesson-card__body">
                    <div className="lesson-card__title">{title}</div>
                    <div className="lesson-card__meta">Matched to your topic & difficulty filters</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <aside className="side-panel">
        <div className="stat-card">
          <div className="stat-card__label">Trend signal</div>
          <div className="stat-card__value">68%</div>
          <div className="stat-card__hint">
            of recent {board} {subject} marks sat in your selected topics
          </div>
        </div>
        <div className="stat-card" style={{ marginTop: 12 }}>
          <div className="stat-card__label">Suggested length</div>
          <div className="stat-card__value">45m</div>
          <div className="stat-card__hint">12 questions · exam-weighted mix</div>
        </div>
      </aside>
    </div>
  );
}
