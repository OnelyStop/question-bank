import type { ReactNode } from "react";
import "./Badge.css";

type Tone = "purple" | "grey" | "green" | "amber";

type Props = {
  children: ReactNode;
  tone?: Tone;
};

export function Badge({ children, tone = "purple" }: Props) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
