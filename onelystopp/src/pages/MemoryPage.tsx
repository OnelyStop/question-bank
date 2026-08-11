import { Button } from "../components/ui/Button";

const WEAK = [
  { topic: "Epigenetics", strength: 42, due: "Due today" },
  { topic: "Hardy–Weinberg", strength: 51, due: "Due tomorrow" },
  { topic: "Respiration calculations", strength: 58, due: "In 2 days" },
  { topic: "Succession evaluation", strength: 63, due: "In 4 days" },
];

export function MemoryPage() {
  return (
    <div className="page page--split">
      <div>
        <div className="page__eyebrow">A* memory</div>
        <h1 className="page__title">Drill weak spots until they stick</h1>
        <p className="page__desc">
          Tracks fragile topics across sessions and schedules spaced drills so A* detail
          doesn’t fade before exam day.
        </p>

        <div className="lesson-list" style={{ marginTop: 24 }}>
          {WEAK.map((w, i) => (
            <div key={w.topic} className={`lesson-card ${i === 0 ? "lesson-card--active" : ""}`}>
              {i === 0 && <div className="lesson-card__start">Drill</div>}
              <div className="lesson-card__icon">
                <span style={{ fontSize: 12, fontWeight: 800, color: "var(--color-primary)" }}>
                  {w.strength}%
                </span>
              </div>
              <div className="lesson-card__body">
                <div className="lesson-card__title">{w.topic}</div>
                <div className="lesson-card__meta">{w.due}</div>
                <div className="progress-bar" style={{ marginTop: 8, maxWidth: 220 }}>
                  <div className="progress-bar__fill" style={{ width: `${w.strength}%` }} />
                </div>
              </div>
              <Button size="sm" variant={i === 0 ? "primary" : "outline"}>
                Practise
              </Button>
            </div>
          ))}
        </div>
      </div>

      <aside className="side-panel">
        <div className="stat-card">
          <div className="stat-card__label">Retention score</div>
          <div className="stat-card__value">74%</div>
          <div className="stat-card__hint">Up 6% this week</div>
        </div>
        <div className="stat-card" style={{ marginTop: 12 }}>
          <div className="stat-card__label">Drills completed</div>
          <div className="stat-card__value">39</div>
          <div className="stat-card__hint">Streak protected · 12 days</div>
        </div>
      </aside>
    </div>
  );
}
