import {
  BarChart3,
  Clock3,
  Lock,
  PlayCircle,
  Smartphone,
  Star,
  Languages,
  CalendarDays,
  Gauge,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { SAMPLE_LESSONS } from "../data/navigation";
import { Button } from "../components/ui/Button";
import { CertificateArt, HeroIllustration } from "../components/ui/Illustrations";
import { LessonList, SectionHeader } from "../components/ui/LessonList";

const AVATARS = [
  { initial: "R", bg: "#5b52f0" },
  { initial: "M", bg: "#f07167" },
  { initial: "S", bg: "#2ec4b6" },
  { initial: "K", bg: "#f5c518" },
];

export function HomePage() {
  const { subject, board, markerLabel } = useApp();

  return (
    <div className="page page--split">
      <div>
        <div className="hero-with-art">
          <div>
            <div className="page__eyebrow">Study path · {board} {subject}</div>
            <h1 className="page__title">Your one-stop revision HQ</h1>
            <p className="page__desc">
              Practise PYQs, generate exam-ready sets, mark written answers against
              official {board} criteria, and drill weak spots until they stick.
            </p>

            <div className="meta-row">
              <span className="meta-row__item">
                <BarChart3 /> Intermediate
              </span>
              <span className="meta-row__item">
                <Clock3 /> 4h 20m path
              </span>
              <span className="meta-row__item">
                <PlayCircle /> 28 sessions
              </span>
              <span className="meta-row__item">
                <Star /> 4.9
              </span>
            </div>

            <div className="cta-row">
              <Link to="/question-bank">
                <Button size="lg">Start revising free</Button>
              </Link>
              <div className="learners">
                <div className="avatar-stack">
                  {AVATARS.map((a) => (
                    <div
                      key={a.initial}
                      className="avatar-stack__item"
                      style={{ background: a.bg, color: a.bg === "#f5c518" ? "#1a1a1f" : "#fff" }}
                    >
                      {a.initial}
                    </div>
                  ))}
                </div>
                29,865 learners
              </div>
            </div>
          </div>
          <div className="hero-art">
            <HeroIllustration />
          </div>
        </div>

        <div className="section-block">
          <SectionHeader
            label="Level 1"
            title="Foundations & exam fluency"
            description="Warm up with topic maps, mark-scheme language, and high-yield drills."
          />
          <LessonList lessons={SAMPLE_LESSONS} />
        </div>

        <div className="section-block">
          <SectionHeader
            label="Level 2"
            title="Tools that score marks"
            description={`Use ${markerLabel}, diagrams, and AI-curated exams when you're ready to push bands.`}
          />
          <div className="grid-3" style={{ marginTop: 4 }}>
            <FeatureTile
              to="/marker"
              title={markerLabel}
              desc={`Exact ${board} mark schemes · photo or typed`}
              tone="#eeedfe"
            />
            <FeatureTile
              to="/diagrams"
              title="Diagram Generator"
              desc="Exam-style labelled visuals from a prompt"
              tone="#fff6e5"
            />
            <FeatureTile
              to="/ai-exams"
              title="AI-Curated Exams"
              desc="Custom papers from PYQs + bank items"
              tone="#e8f7ef"
            />
          </div>
        </div>
      </div>

      <aside className="side-panel">
        <div className="cert-card">
          <div className="cert-card__art">
            <CertificateArt />
            <Lock
              size={16}
              style={{ position: "absolute", top: 12, right: 12, color: "#8f8f9a" }}
            />
          </div>
          <div className="cert-card__title">A* readiness certificate</div>
          <div className="cert-card__sub">Complete Level 1 to unlock</div>
        </div>

        <div className="detail-list">
          <div className="detail-list__item">
            <CalendarDays />
            <div>
              <strong>Last updated</strong>
              Aug 2026 · {board} spec
            </div>
          </div>
          <div className="detail-list__item">
            <Languages />
            <div>
              <strong>Language</strong>
              English
            </div>
          </div>
          <div className="detail-list__item">
            <Smartphone />
            <div>
              <strong>Access</strong>
              Desktop & mobile
            </div>
          </div>
          <div className="detail-list__item">
            <Gauge />
            <div>
              <strong>Pace</strong>
              Self-paced
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

function FeatureTile({
  to,
  title,
  desc,
  tone,
}: {
  to: string;
  title: string;
  desc: string;
  tone: string;
}) {
  return (
    <Link
      to={to}
      className="panel"
      style={{
        display: "block",
        transition: "transform 160ms ease, box-shadow 160ms ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 24px rgba(26,26,31,0.08)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "";
        e.currentTarget.style.boxShadow = "";
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: tone,
          marginBottom: 12,
        }}
      />
      <div className="panel__title">{title}</div>
      <div className="panel__sub">{desc}</div>
    </Link>
  );
}
