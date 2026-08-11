import { useMemo, useState } from "react";
import { Filter, Search } from "lucide-react";
import { useApp } from "../context/AppContext";
import { TOPICS } from "../data/navigation";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";

const DIFFICULTIES = ["All", "Easy", "Medium", "Hard"];
const YEARS = ["All years", "2025", "2024", "2023", "2022", "2021", "2020"];

const QUESTIONS = [
  {
    id: "q1",
    topic: "Cell Biology",
    year: 2024,
    difficulty: "Medium",
    exam: "Paper 1",
    text: "Explain how the structure of a mitochondrion is related to its function in aerobic respiration.",
    marks: 6,
  },
  {
    id: "q2",
    topic: "Genetics",
    year: 2023,
    difficulty: "Hard",
    exam: "Paper 2",
    text: "Discuss how epigenetic changes can affect gene expression without altering the DNA sequence.",
    marks: 9,
  },
  {
    id: "q3",
    topic: "Ecology",
    year: 2025,
    difficulty: "Easy",
    exam: "Paper 1",
    text: "Define carrying capacity and describe two density-dependent factors that can limit population growth.",
    marks: 4,
  },
  {
    id: "q4",
    topic: "Organic Chemistry",
    year: 2022,
    difficulty: "Medium",
    exam: "Paper 2",
    text: "Outline the mechanism for nucleophilic substitution of a primary halogenoalkane.",
    marks: 5,
  },
  {
    id: "q5",
    topic: "Mechanics",
    year: 2024,
    difficulty: "Hard",
    exam: "Paper 1",
    text: "A projectile is launched at 28 m/s at 40°. Calculate the maximum height reached.",
    marks: 4,
  },
  {
    id: "q6",
    topic: "Macroeconomics",
    year: 2023,
    difficulty: "Medium",
    exam: "Paper 2",
    text: "Evaluate the effectiveness of expansionary fiscal policy in reducing unemployment.",
    marks: 25,
  },
];

export function QuestionBankPage() {
  const { subject, board } = useApp();
  const [difficulty, setDifficulty] = useState("All");
  const [year, setYear] = useState("All years");
  const [topic, setTopic] = useState("All topics");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>("q1");

  const filtered = useMemo(() => {
    return QUESTIONS.filter((q) => {
      if (difficulty !== "All" && q.difficulty !== difficulty) return false;
      if (year !== "All years" && String(q.year) !== year) return false;
      if (topic !== "All topics" && q.topic !== topic) return false;
      if (query && !q.text.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [difficulty, year, topic, query]);

  return (
    <div className="page">
      <div className="page__eyebrow">Question bank · {board}</div>
      <h1 className="page__title">Browse by topic, difficulty & year</h1>
      <p className="page__desc">
        Curated {subject} questions with detailed solution walkthroughs — sorted the
        way examiners structure papers.
      </p>

      <div className="panel" style={{ marginTop: 24 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div className="topbar__search" style={{ flex: 1, minWidth: 220, maxWidth: "none" }}>
            <Search size={16} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search question stems…"
            />
          </div>
          <Button variant="outline" leftIcon={<Filter size={15} />}>
            Filters
          </Button>
        </div>

        <div style={{ marginTop: 16 }}>
          <div className="chip-row">
            {DIFFICULTIES.map((d) => (
              <Chip key={d} active={difficulty === d} onClick={() => setDifficulty(d)}>
                {d}
              </Chip>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 12 }} className="chip-row">
          {YEARS.map((y) => (
            <Chip key={y} active={year === y} onClick={() => setYear(y)}>
              {y}
            </Chip>
          ))}
        </div>

        <div style={{ marginTop: 12 }} className="chip-row">
          <Chip active={topic === "All topics"} onClick={() => setTopic("All topics")}>
            All topics
          </Chip>
          {TOPICS.slice(0, 6).map((t) => (
            <Chip key={t} active={topic === t} onClick={() => setTopic(t)}>
              {t}
            </Chip>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 18, color: "var(--color-text-muted)", fontSize: 13, fontWeight: 600 }}>
        {filtered.length} questions
      </div>

      <div className="lesson-list" style={{ marginTop: 12 }}>
        {filtered.map((q) => {
          const open = openId === q.id;
          return (
            <div
              key={q.id}
              className={`lesson-card ${open ? "lesson-card--active" : ""}`}
              onClick={() => setOpenId(open ? null : q.id)}
              style={{ cursor: "pointer", alignItems: "flex-start" }}
            >
              {open && <div className="lesson-card__start">Open</div>}
              <div className="lesson-card__icon" style={{ marginTop: 2 }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: "var(--color-primary)" }}>
                  {q.marks}m
                </span>
              </div>
              <div className="lesson-card__body">
                <div className="lesson-card__title">{q.text}</div>
                <div className="lesson-card__meta">
                  {q.topic} · {q.year} · {q.exam} · {q.difficulty}
                </div>
                {open && (
                  <div
                    style={{
                      marginTop: 12,
                      padding: 14,
                      borderRadius: 10,
                      background: "var(--color-bg-subtle)",
                      color: "var(--color-text-secondary)",
                      fontSize: 14,
                      lineHeight: 1.55,
                    }}
                  >
                    <strong style={{ color: "var(--color-text)" }}>Solution outline</strong>
                    <p style={{ marginTop: 6 }}>
                      Award marks for each linked point to the mark scheme. Structure AO1
                      knowledge first, then apply to the scenario (AO2), and finish with a
                      justified evaluation where the question asks for discussion.
                    </p>
                    <div style={{ marginTop: 12 }}>
                      <Button size="sm">Practise this question</Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
