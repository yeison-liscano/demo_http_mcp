import { useState } from "react";
import type { ToolCallEvent, ToolResultEvent } from "../types";

interface ToolCardProps {
  call: ToolCallEvent;
  result?: ToolResultEvent;
}

export default function ToolCard({ call, result }: ToolCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isLoading = !result;

  const argsSummary = Object.entries(call.args)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");

  return (
    <div className="tool-card">
      <button
        className="tool-card__header"
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <span className="tool-card__icon">
          {isLoading ? (
            <span className="tool-card__spinner" />
          ) : (
            <span className="tool-card__check">&#10003;</span>
          )}
        </span>
        <span className="tool-card__name">{call.tool_name}</span>
        <span className="tool-card__args-summary">({argsSummary})</span>
        <span
          className={`tool-card__chevron ${expanded ? "tool-card__chevron--open" : ""}`}
        >
          &#9656;
        </span>
      </button>

      {expanded && (
        <div className="tool-card__body">
          <div className="tool-card__section">
            <div className="tool-card__section-label">Arguments</div>
            <pre className="tool-card__json">
              {JSON.stringify(call.args, null, 2)}
            </pre>
          </div>
          {result && (
            <div className="tool-card__section">
              <div className="tool-card__section-label">Result</div>
              <pre className="tool-card__json">
                {JSON.stringify(result.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
