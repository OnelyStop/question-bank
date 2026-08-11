import { useApp } from "../context/AppContext";

const CHAPTERS = [
  {
    title: "3.1 Biological molecules",
    points: ["Monomers & polymers", "Carbohydrates", "Lipids", "Proteins & enzymes"],
  },
  {
    title: "3.2 Cells",
    points: ["Cell structure", "Transport across membranes", "Cell recognition & immune"],
  },
  {
    title: "3.3 Organisms exchange substances",
    points: ["Surface area to volume", "Gas exchange", "Digestion & absorption"],
  },
];

export function RevisionPage() {
  const { subject, board } = useApp();

  return (
    <div className="page">
      <div className="page__eyebrow">Revision guide</div>
      <h1 className="page__title">Spec-aligned notes</h1>
      <p className="page__desc">
        Written the way {board} examiners want them for {subject} — crisp definitions,
        linked explanations, and mark-scheme phrasing built in.
      </p>

      <div className="grid-3" style={{ marginTop: 24 }}>
        {CHAPTERS.map((ch) => (
          <article key={ch.title} className="panel">
            <div className="panel__title">{ch.title}</div>
            <ul style={{ marginTop: 12, display: "grid", gap: 8 }}>
              {ch.points.map((p) => (
                <li
                  key={p}
                  style={{
                    fontSize: 14,
                    color: "var(--color-text-secondary)",
                    paddingLeft: 12,
                    borderLeft: "2px solid var(--color-primary-muted)",
                  }}
                >
                  {p}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}
