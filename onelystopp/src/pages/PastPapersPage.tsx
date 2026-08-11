import { useState } from "react";
import { Search } from "lucide-react";
import { useApp } from "../context/AppContext";
import { Chip } from "../components/ui/Chip";

const PAPERS = [
  { year: 2025, paper: "Paper 1", topics: "Cell biology, Biological molecules", difficulty: "Medium", qs: 18 },
  { year: 2024, paper: "Paper 2", topics: "Genetics, Evolution", difficulty: "Hard", qs: 16 },
  { year: 2024, paper: "Paper 1", topics: "Exchange, Transport", difficulty: "Medium", qs: 20 },
  { year: 2023, paper: "Paper 2", topics: "Ecology, Energy transfer", difficulty: "Easy", qs: 15 },
  { year: 2022, paper: "Paper 1", topics: "Cells, Immunity", difficulty: "Medium", qs: 19 },
  { year: 2021, paper: "Paper 2", topics: "Gene expression, Populations", difficulty: "Hard", qs: 17 },
];

export function PastPapersPage() {
  const { board, subject } = useApp();
  const [q, setQ] = useState("");

  const filtered = PAPERS.filter(
    (p) =>
      !q ||
      `${p.year} ${p.paper} ${p.topics}`.toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <div className="page">
      <div className="page__eyebrow">Past paper finder · New</div>
      <h1 className="page__title">2,000+ questions, searchable</h1>
      <p className="page__desc">
        Find {board} {subject} past paper items by topic, year and difficulty — then jump
        straight into practice.
      </p>

      <div className="panel" style={{ marginTop: 24 }}>
        <div className="topbar__search" style={{ maxWidth: "none" }}>
          <Search size={16} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by year, paper, or topic…"
          />
        </div>
        <div className="chip-row" style={{ marginTop: 14 }}>
          {["All years", "Paper 1", "Paper 2", "Hard only"].map((c, i) => (
            <Chip key={c} active={i === 0}>
              {c}
            </Chip>
          ))}
        </div>
      </div>

      <div className="lesson-list" style={{ marginTop: 18 }}>
        {filtered.map((p, i) => (
          <div key={`${p.year}-${p.paper}`} className={`lesson-card ${i === 1 ? "lesson-card--active" : ""}`}>
            {i === 1 && <div className="lesson-card__start">Open</div>}
            <div className="lesson-card__icon">
              <span style={{ fontSize: 11, fontWeight: 800 }}>{p.year}</span>
            </div>
            <div className="lesson-card__body">
              <div className="lesson-card__title">
                {board} {subject} {p.year} · {p.paper}
              </div>
              <div className="lesson-card__meta">
                {p.topics} · {p.difficulty} · {p.qs} questions
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
