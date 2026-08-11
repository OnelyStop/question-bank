import { useState } from "react";
import { Mic, Volume2 } from "lucide-react";
import { useApp } from "../context/AppContext";
import { Button } from "../components/ui/Button";
import { HeroIllustration } from "../components/ui/Illustrations";

const QUESTIONS = [
  "Walk me through how you would approach an unfamiliar 6-mark data question.",
  "Explain a concept from your weakest topic as if teaching a classmate.",
  "What mark-scheme phrases would you use to secure evaluation marks?",
];

export function InterviewPage() {
  const { subject } = useApp();
  const [listening, setListening] = useState(false);
  const [index, setIndex] = useState(0);
  const [transcript, setTranscript] = useState("");

  return (
    <div className="page page--split">
      <div>
        <div className="hero-with-art">
          <div>
            <div className="page__eyebrow">AI interview · Beta</div>
            <h1 className="page__title">Simulate the real conversation</h1>
            <p className="page__desc">
              Practise explaining {subject} out loud with STT and TTS — build fluency for
              orals, mocks, and interview-style probing.
            </p>
            <div className="cta-row">
              <Button
                size="lg"
                leftIcon={<Mic size={16} />}
                onClick={() => setListening((v) => !v)}
              >
                {listening ? "Stop listening" : "Start interview"}
              </Button>
              <Button variant="outline" size="lg" leftIcon={<Volume2 size={16} />}>
                Replay question
              </Button>
            </div>
          </div>
          <div className="hero-art">
            <HeroIllustration variant="interview" />
          </div>
        </div>

        <div className="panel" style={{ marginTop: 28 }}>
          <div className="page__eyebrow">Question {index + 1} of {QUESTIONS.length}</div>
          <div className="panel__title" style={{ fontSize: 20, marginTop: 6 }}>
            {QUESTIONS[index]}
          </div>

          <div
            style={{
              marginTop: 20,
              height: 64,
              borderRadius: 14,
              background: listening ? "var(--color-primary-soft)" : "var(--color-bg-subtle)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              transition: "background 200ms ease",
            }}
          >
            {[8, 16, 28, 40, 24, 14, 10, 22, 34, 18, 12].map((h, i) => (
              <span
                key={i}
                style={{
                  width: 6,
                  height: listening ? h : 8,
                  borderRadius: 99,
                  background: "var(--color-primary)",
                  opacity: listening ? 1 : 0.35,
                  transition: "height 180ms ease",
                }}
              />
            ))}
          </div>

          <div className="field" style={{ marginTop: 16 }}>
            <label>Live transcript (STT)</label>
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder={listening ? "Listening…" : "Your spoken answer will appear here"}
            />
          </div>

          <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
            <Button
              variant="secondary"
              onClick={() => setIndex((i) => (i + 1) % QUESTIONS.length)}
            >
              Next question
            </Button>
            <Button variant="outline">Get feedback</Button>
          </div>
        </div>
      </div>

      <aside className="side-panel">
        <div className="stat-card">
          <div className="stat-card__label">Session</div>
          <div className="stat-card__value">12m</div>
          <div className="stat-card__hint">Avg response clarity · 78%</div>
          <div className="progress-bar" style={{ marginTop: 12 }}>
            <div className="progress-bar__fill" style={{ width: "78%" }} />
          </div>
        </div>
      </aside>
    </div>
  );
}
