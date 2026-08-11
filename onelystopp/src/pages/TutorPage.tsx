import { useState } from "react";
import { Send } from "lucide-react";
import { useApp } from "../context/AppContext";
import { Button } from "../components/ui/Button";

type Msg = { role: "user" | "assistant"; text: string };

export function TutorPage() {
  const { subject, board } = useApp();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      text: `I'm your ${board} ${subject} tutor — trained on past papers, mark schemes and the specification. Ask for explanations, mark-scheme language, or a quick drill.`,
    },
  ]);

  const send = () => {
    if (!input.trim()) return;
    const userText = input.trim();
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", text: userText },
      {
        role: "assistant",
        text: `For ${board} ${subject}, examiners typically want a clear AO1 statement first, then application to the data/scenario. Here's a mark-scheme shaped answer outline you can adapt…`,
      },
    ]);
  };

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <div className="page__eyebrow">AI tutor</div>
      <h1 className="page__title">Trained on your board</h1>
      <p className="page__desc">
        Not a generic chatbot — grounded in {board} papers, schemes and the {subject}{" "}
        spec.
      </p>

      <div className="panel" style={{ marginTop: 24, minHeight: 420, display: "flex", flexDirection: "column" }}>
        <div style={{ flex: 1, display: "grid", gap: 12, overflow: "auto" }}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                maxWidth: "85%",
                justifySelf: m.role === "user" ? "end" : "start",
                padding: "12px 14px",
                borderRadius: 12,
                background: m.role === "user" ? "var(--color-primary)" : "var(--color-bg-subtle)",
                color: m.role === "user" ? "#fff" : "var(--color-text)",
                fontSize: 14,
                lineHeight: 1.5,
              }}
            >
              {m.text}
            </div>
          ))}
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask anything about this paper / topic…"
            style={{
              flex: 1,
              height: 44,
              borderRadius: 10,
              border: "1px solid var(--color-border)",
              padding: "0 12px",
            }}
          />
          <Button leftIcon={<Send size={15} />} onClick={send}>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
