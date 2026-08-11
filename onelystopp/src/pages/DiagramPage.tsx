import { useState } from "react";
import { Wand2 } from "lucide-react";
import { useApp } from "../context/AppContext";
import { Button } from "../components/ui/Button";
import { HeroIllustration } from "../components/ui/Illustrations";

export function DiagramPage() {
  const { subject, board } = useApp();
  const [prompt, setPrompt] = useState(
    "Draw a labelled diagram of a mitochondrion showing outer membrane, inner membrane, cristae and matrix.",
  );
  const [generated, setGenerated] = useState(false);

  return (
    <div className="page page--split">
      <div>
        <div className="hero-with-art">
          <div>
            <div className="page__eyebrow">Diagram generator · {subject}</div>
            <h1 className="page__title">Exam-style diagrams from a prompt</h1>
            <p className="page__desc">
              See the labelled visual an examiner expects — then pair it with the marker
              when a missing diagram cost you marks.
            </p>
          </div>
          <div className="hero-art">
            <HeroIllustration variant="diagram" />
          </div>
        </div>

        <div className="panel" style={{ marginTop: 24 }}>
          <div className="field">
            <label>Describe the diagram</label>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          </div>
          <div style={{ marginTop: 14 }}>
            <Button size="lg" leftIcon={<Wand2 size={16} />} onClick={() => setGenerated(true)}>
              Generate labelled diagram
            </Button>
          </div>
        </div>

        {generated && (
          <div className="panel" style={{ marginTop: 18 }}>
            <div className="panel__title">Preview · {board} style</div>
            <div
              style={{
                marginTop: 14,
                borderRadius: 16,
                border: "1px solid var(--color-border)",
                background: "var(--color-bg-subtle)",
                minHeight: 280,
                display: "grid",
                placeItems: "center",
                padding: 24,
              }}
            >
              <svg viewBox="0 0 420 240" width="100%" style={{ maxWidth: 480 }}>
                <ellipse cx="210" cy="120" rx="150" ry="85" fill="#fff" stroke="#1a1a1f" strokeWidth="3" />
                <ellipse cx="210" cy="120" rx="118" ry="62" fill="none" stroke="#1a1a1f" strokeWidth="3" />
                <path d="M120 120c20-28 40-28 60 0s40 28 60 0 40-28 60 0" stroke="#5b52f0" strokeWidth="3" fill="none" />
                <path d="M130 145c18-20 36-20 54 0" stroke="#5b52f0" strokeWidth="3" fill="none" />
                <circle cx="210" cy="120" r="10" fill="#f07167" stroke="#1a1a1f" strokeWidth="2" />
                <line x1="360" y1="60" x2="300" y2="80" stroke="#1a1a1f" strokeWidth="2" />
                <text x="366" y="58" fontSize="12" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700">outer membrane</text>
                <line x1="60" y1="50" x2="120" y2="85" stroke="#1a1a1f" strokeWidth="2" />
                <text x="8" y="46" fontSize="12" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700">cristae</text>
                <line x1="210" y1="120" x2="210" y2="190" stroke="#1a1a1f" strokeWidth="2" />
                <text x="190" y="208" fontSize="12" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700">matrix</text>
              </svg>
            </div>
            <div className="panel__sub" style={{ marginTop: 12 }}>
              Labels placed for exam credit. Export PNG or drop into revision notes.
            </div>
          </div>
        )}
      </div>

      <aside className="side-panel">
        <div className="stat-card">
          <div className="stat-card__label">Pairs with</div>
          <div className="stat-card__value" style={{ fontSize: 18 }}>
            Answer Marker
          </div>
          <div className="stat-card__hint">
            When feedback flags a missing / wrong diagram, regenerate it here.
          </div>
        </div>
      </aside>
    </div>
  );
}
