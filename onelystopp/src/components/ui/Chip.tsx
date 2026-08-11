import type { ReactNode } from "react";
import "./Chip.css";

type Props = {
  children: ReactNode;
  active?: boolean;
  onClick?: () => void;
};

export function Chip({ children, active, onClick }: Props) {
  return (
    <button
      type="button"
      className={`chip ${active ? "chip--active" : ""}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
