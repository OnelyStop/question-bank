import { useApp } from "../context/AppContext";

const TOPICS = [
  { name: "Cell Biology", practised: 86, accuracy: 78, exam: 72 },
  { name: "Genetics", practised: 64, accuracy: 61, exam: 55 },
  { name: "Ecology", practised: 72, accuracy: 84, exam: 80 },
  { name: "Bioenergetics", practised: 48, accuracy: 70, exam: 66 },
  { name: "Homeostasis", practised: 55, accuracy: 59, exam: 52 },
];

export function ProgressPage() {
  const { subject } = useApp();

  return (
    <div className="page">
      <div className="page__eyebrow">Progress tracker</div>
      <h1 className="page__title">Topic-wise performance</h1>
      <p className="page__desc">
        Track questions practised and fold in exam scores to see how well you understand
        each {subject} topic.
      </p>

      <div className="grid-4" style={{ marginTop: 24 }}>
        {[
          { label: "Questions practised", value: "1,284" },
          { label: "Avg accuracy", value: "71%" },
          { label: "Mock average", value: "68%" },
          { label: "Weak topics", value: "3" },
        ].map((s) => (
          <div key={s.label} className="stat-card">
            <div className="stat-card__label">{s.label}</div>
            <div className="stat-card__value">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <div className="panel__title">Insight by topic</div>
        <div className="panel__sub">Practice accuracy vs integrated exam scores</div>
        <div style={{ marginTop: 18, display: "grid", gap: 16 }}>
          {TOPICS.map((t) => (
            <div key={t.name}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  marginBottom: 8,
                  fontSize: 14,
                }}
              >
                <strong>{t.name}</strong>
                <span style={{ color: "var(--color-text-secondary)" }}>
                  {t.practised} Qs · {t.accuracy}% practise · {t.exam}% exams
                </span>
              </div>
              <div className="progress-bar">
                <div className="progress-bar__fill" style={{ width: `${t.accuracy}%` }} />
              </div>
              <div className="progress-bar" style={{ marginTop: 6, opacity: 0.7 }}>
                <div
                  className="progress-bar__fill"
                  style={{ width: `${t.exam}%`, background: "#2ec4b6" }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
