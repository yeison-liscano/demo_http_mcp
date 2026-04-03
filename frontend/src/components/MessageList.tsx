import { useEffect, useRef } from "react";
import type { StreamEvent, ToolCallEvent, ToolResultEvent } from "../types";
import MessageBubble from "./MessageBubble";
import ToolCard from "./ToolCard";

interface MessageListProps {
  events: StreamEvent[];
}

export default function MessageList({ events }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  if (events.length === 0) {
    return (
      <div className="message-list message-list--empty">
        <p>No messages yet. Ask me about vulnerabilities in any dependency!</p>
      </div>
    );
  }

  // Build a map of tool_call_id → result for pairing
  const resultMap = new Map<string, ToolResultEvent>();
  for (const e of events) {
    if (e.type === "tool_result") {
      resultMap.set(e.tool_call_id, e);
    }
  }

  // Track which tool_call_ids we've already rendered
  const renderedToolCalls = new Set<string>();

  return (
    <div className="message-list">
      {events.map((event, i) => {
        if (event.type === "text") {
          return (
            <MessageBubble
              key={`text-${event.role}-${event.timestamp}`}
              message={event}
            />
          );
        }
        if (event.type === "tool_call") {
          renderedToolCalls.add(event.tool_call_id);
          return (
            <ToolCard
              key={`tool-${event.tool_call_id}`}
              call={event}
              result={resultMap.get(event.tool_call_id)}
            />
          );
        }
        // tool_result: skip if already rendered with its tool_call
        if (event.type === "tool_result") {
          if (renderedToolCalls.has(event.tool_call_id)) return null;
          // Orphan result (no call seen) — render standalone
          const syntheticCall: ToolCallEvent = {
            type: "tool_call",
            tool_call_id: event.tool_call_id,
            tool_name: event.tool_name,
            args: event.args,
            timestamp: event.timestamp,
          };
          return (
            <ToolCard
              key={`tool-${event.tool_call_id}-${i}`}
              call={syntheticCall}
              result={event}
            />
          );
        }
        return null;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
