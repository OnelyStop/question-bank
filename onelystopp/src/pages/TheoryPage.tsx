import { useState } from "react";
import { useApp } from "../context/AppContext";
import { Chip } from "../components/ui/Chip";

const ITEMS = [
  {
    title: "Respiration shortcut map",
    type: "Trick",
    body: "Glycolysis in cytoplasm → Link + Krebs in matrix → ETC on inner membrane. If the question says ‘precise location’, name the compartment.",
  },
  {
    title: "Antibody structure (theory)",
    type: "Theory",
    body: "4 polypeptide chains, variable regions bind antigen, hinge allows flexibility. Constant region determines class.",
  },
  {
    title: "Hard calculation pattern",
    type: "Trick",
    body: "For magnification: I = A × M. Rearrange carefully and convert units before substituting.",
  },
  {
    title: "Succession stages",
    type: "Theory",
    body: "Pioneer species → intermediate communities → climax. Abiotic conditions change as biomass accumulates.",
  },
];

export function TheoryPage() {
  const { subject } = useApp();
  const [filter, setFilter] = useState("All");

  const filtered =
    filter === "All" ? ITEMS : ITEMS.filter((i) => i.type === filter);

  return (
    <div className="page">
      <div className="page__eyebrow">Theory & tricks</div>
      <h1 className="page__title">Shortcuts examiners reward</h1>
      <p className="page__desc">
        Spec-aligned theory, coaching shortcuts, and problem-solving tricks for {subject} —
        aggregated so you revise the way marks are actually awarded.
      </p>

      <div className="chip-row" style={{ marginTop: 20 }}>
        {["All", "Theory", "Trick"].map((f) => (
          <Chip key={f} active={filter === f} onClick={() => setFilter(f)}>
            {f}
          </Chip>
        ))}
      </div>

      <div className="grid-2" style={{ marginTop: 18 }}>
        {filtered.map((item) => (
          <article key={item.title} className="panel">
            <div className="page__eyebrow">{item.type}</div>
            <div className="panel__title" style={{ marginTop: 4 }}>
              {item.title}
            </div>
            <p className="panel__sub" style={{ marginTop: 10, lineHeight: 1.55 }}>
              {item.body}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
