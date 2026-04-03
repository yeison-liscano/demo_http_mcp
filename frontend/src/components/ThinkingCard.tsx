import { useState } from "react";
import type { ThinkingEvent } from "../types";

interface ThinkingCardProps {
  event: ThinkingEvent;
}

export default function ThinkingCard({ event }: ThinkingCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="thinking-card">
      <button
        className="thinking-card__header"
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <span className="thinking-card__label">Thinking...</span>
        <span
          className={`thinking-card__chevron ${expanded ? "thinking-card__chevron--open" : ""}`}
        >
          &#9656;
        </span>
      </button>

      {expanded && (
        <div className="thinking-card__body">
          {event.content}
        </div>
      )}
    </div>
  );
}
