import { useState } from "react";
import { Camera, Type } from "lucide-react";
import { useApp } from "../context/AppContext";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { HeroIllustration } from "../components/ui/Illustrations";

export function MarkerPage() {
  const { subject, board, markerLabel } = useApp();
  const [mode, setMode] = useState<"photo" | "text">("text");
  const [answer, setAnswer] = useState(
    "Mitochondria have a double membrane; the inner membrane is folded into cristae which increase surface area for oxidative phosphorylation. The matrix contains enzymes for the Krebs cycle and mitochondrial DNA.",
  );
  const [marked, setMarked] = useState(false);

  return (
    <div className="page page--split">
      <div>
        <div className="hero-with-art">
          <div>
            <div className="page__eyebrow">{markerLabel}</div>
            <h1 className="page__title">Mark against the real scheme</h1>
            <p className="page__desc">
              Submit a written {subject} answer and get a mark plus band-level feedback
              using exact {board} marking criteria — trained on 2017–2025 papers, schemes
              and the full specification.
            </p>
            <div className="cta-row">
              <Chip active={mode === "photo"} onClick={() => setMode("photo")}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Camera size={14} /> Photo upload
                </span>
              </Chip>
              <Chip active={mode === "text"} onClick={() => setMode("text")}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Type size={14} /> Typed / pasted
                </span>
              </Chip>
            </div>
          </div>
          <div className="hero-art">
            <HeroIllustration variant="marker" />
          </div>
        </div>

        <div className="panel" style={{ marginTop: 28 }}>
          <div className="panel__title">
            {mode === "photo" ? "Snap your handwritten answer" : "Paste your answer"}
          </div>
          <div className="panel__sub">
            Instant feedback using exact {board} marking criteria
          </div>

          {mode === "photo" ? (
            <div
              className="empty-state"
              style={{ marginTop: 16, cursor: "pointer" }}
            >
              <Camera size={28} style={{ margin: "0 auto 10px", color: "var(--color-primary)" }} />
              Drop a photo here or click to upload
              <div style={{ marginTop: 6, fontSize: 13 }}>JPG, PNG · handwriting OCR supported</div>
            </div>
          ) : (
            <div className="field" style={{ marginTop: 16 }}>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Paste your exam answer…"
              />
            </div>
          )}

          <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
            <Button size="lg" onClick={() => setMarked(true)}>
              Mark answer
            </Button>
            <Button variant="outline" size="lg" onClick={() => setMarked(false)}>
              Clear
            </Button>
          </div>
        </div>

        {marked && (
          <div className="section-block">
            <div
              className="panel"
              style={{
                borderColor: "var(--color-primary)",
                boxShadow: "0 0 0 3px var(--color-primary-soft)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                <div>
                  <div className="page__eyebrow">Result</div>
                  <div className="page__title" style={{ fontSize: 28 }}>
                    Essay marked · 23/25
                  </div>
                </div>
                <div className="stat-card" style={{ minWidth: 120 }}>
                  <div className="stat-card__label">Band</div>
                  <div className="stat-card__value">Top</div>
                </div>
              </div>

              <div className="grid-2" style={{ marginTop: 18 }}>
                {[
                  { label: "Knowledge", score: "8/8" },
                  { label: "Application", score: "7/8" },
                  { label: "Analysis", score: "5/5" },
                  { label: "Evaluation", score: "3/4" },
                ].map((b) => (
                  <div key={b.label} className="stat-card">
                    <div className="stat-card__label">{b.label}</div>
                    <div className="stat-card__value" style={{ fontSize: 20 }}>
                      {b.score}
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 18 }}>
                <div className="panel__title">Targeted improvement notes</div>
                <ul style={{ marginTop: 10, display: "grid", gap: 8 }}>
                  {[
                    "Add one comparative evaluation point to push the final mark to 25.",
                    "Link cristae surface area explicitly to ATP yield for full AO2 credit.",
                    "Avoid restating the question stem — spend words on mechanism detail.",
                  ].map((note) => (
                    <li
                      key={note}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 10,
                        background: "var(--color-bg-subtle)",
                        fontSize: 14,
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      {note}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>

      <aside className="side-panel">
        <div className="cert-card">
          <div className="cert-card__title">Trained on</div>
          <div className="cert-card__sub" style={{ marginTop: 8, lineHeight: 1.5 }}>
            2017–2025 past papers, official mark schemes, and the full {board} {subject}{" "}
            specification — not a generic chatbot.
          </div>
        </div>
        <div className="detail-list">
          <div className="detail-list__item">
            <div>
              <strong>Board</strong>
              {board}
            </div>
          </div>
          <div className="detail-list__item">
            <div>
              <strong>Subject</strong>
              {subject}
            </div>
          </div>
          <div className="detail-list__item">
            <div>
              <strong>Feature name</strong>
              Renames per subject ({markerLabel})
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
