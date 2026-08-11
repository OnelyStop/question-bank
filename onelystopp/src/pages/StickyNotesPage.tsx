import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "../components/ui/Button";

type Note = {
  id: string;
  title: string;
  body: string;
  color: string;
  updated: string;
};

const COLORS = ["#FFF3B0", "#FFD6E0", "#CDE7FF", "#D8F3DC", "#EDE7F6"];

const INITIAL: Note[] = [
  {
    id: "1",
    title: "Cristae = SA",
    body: "Inner membrane folds → more ETC proteins → more ATP. Always link structure to function in 4–6 markers.",
    color: COLORS[0],
    updated: "Today",
  },
  {
    id: "2",
    title: "Command: Evaluate",
    body: "Needs judgement + justification. Use ‘however’, ‘depends on’, ‘in the short run…’.",
    color: COLORS[1],
    updated: "Yesterday",
  },
  {
    id: "3",
    title: "Hard topic: Epigenetics",
    body: "Methylation / acetylation change expression without changing base sequence. Revisit Friday.",
    color: COLORS[2],
    updated: "Mon",
  },
];

export function StickyNotesPage() {
  const [notes, setNotes] = useState(INITIAL);

  const addNote = () => {
    setNotes((prev) => [
      {
        id: String(Date.now()),
        title: "New sticky",
        body: "Capture a concept, trick, or mark-scheme phrase to revisit later.",
        color: COLORS[prev.length % COLORS.length],
        updated: "Just now",
      },
      ...prev,
    ]);
  };

  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div className="page__eyebrow">Sticky notes</div>
          <h1 className="page__title">Pin what matters</h1>
          <p className="page__desc">
            Track important concepts and revisit them before mocks — your personal wall of
            high-yield reminders.
          </p>
        </div>
        <Button leftIcon={<Plus size={16} />} onClick={addNote}>
          New note
        </Button>
      </div>

      <div className="sticky-board" style={{ marginTop: 28 }}>
        {notes.map((note) => (
          <article key={note.id} className="note-card" style={{ background: note.color }}>
            <div className="note-card__title">{note.title}</div>
            <div className="note-card__body">{note.body}</div>
            <div className="note-card__meta">{note.updated}</div>
          </article>
        ))}
      </div>
    </div>
  );
}
