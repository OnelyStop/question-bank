import { Check, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

type Lesson = {
  id: string;
  title: string;
  meta?: string;
  done?: boolean;
  active?: boolean;
  icon?: ReactNode;
};

export function LessonList({ lessons }: { lessons: Lesson[] }) {
  return (
    <div className="lesson-list">
      {lessons.map((lesson) => (
        <div
          key={lesson.id}
          className={`lesson-card ${lesson.active ? "lesson-card--active" : ""}`}
        >
          {lesson.active && <div className="lesson-card__start">Start</div>}
          <div className="lesson-card__icon">{lesson.icon ?? <LessonGlyph id={lesson.id} />}</div>
          <div className="lesson-card__body">
            <div className="lesson-card__title">{lesson.title}</div>
            {lesson.meta && <div className="lesson-card__meta">{lesson.meta}</div>}
          </div>
          <div
            className={`lesson-card__status ${lesson.done ? "lesson-card__status--done" : ""}`}
          >
            {lesson.done ? <Check size={13} strokeWidth={2.5} /> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function LessonGlyph({ id }: { id: string }) {
  const colors = ["#5b52f0", "#f5c518", "#f07167", "#2ec4b6", "#1e2a44"];
  const color = colors[Number(id) % colors.length];
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="4" width="18" height="16" rx="4" fill={color} opacity="0.15" />
      <rect x="6" y="8" width="12" height="2.5" rx="1.25" fill={color} />
      <rect x="6" y="13" width="8" height="2.5" rx="1.25" fill={color} opacity="0.55" />
    </svg>
  );
}

export function SectionHeader({
  label,
  title,
  description,
}: {
  label: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="section-block__header">
      <div>
        <div className="section-block__label">{label}</div>
        <div className="section-block__title">{title}</div>
        {description && <div className="section-block__desc">{description}</div>}
      </div>
      <ChevronDown size={18} color="#8f8f9a" />
    </div>
  );
}
