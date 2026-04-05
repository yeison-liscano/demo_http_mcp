import type { TextEvent as AppTextEvent, StreamEvent } from "./types";

const API_BASE = "/api";

export async function fetchChatHistory(): Promise<StreamEvent[]> {
  const response = await fetch(`${API_BASE}/chat/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch chat history: ${response.status}`);
  }
  const text = await response.text();
  return text
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as StreamEvent);
}

export async function sendChatMessage(
  prompt: string,
  onChunk: (events: StreamEvent[]) => void,
): Promise<void> {
  const body = new FormData();
  body.append("prompt", prompt);

  const response = await fetch(`${API_BASE}/chat/`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Unexpected response: ${response.status}`, text);
    throw new Error(`Unexpected response: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let userMessage: AppTextEvent | null = null;
  let modelContent = "";
  let modelTimestamp = "";
  // Track middle events (thinking, tool_call, tool_result) in arrival order.
  // Consecutive thinking chunks share one entry; a non-thinking event in
  // between starts a new thinking block the next time one arrives.
  const middleEvents: StreamEvent[] = [];
  let activeThinkingIdx = -1; // index into middleEvents for current thinking block

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.trim().length === 0) continue;
      const chunk = JSON.parse(line) as StreamEvent;

      switch (chunk.type) {
        case "text":
          if (chunk.role === "user") {
            userMessage = chunk;
          } else {
            if (!modelTimestamp) modelTimestamp = chunk.timestamp;
            modelContent += chunk.content;
          }
          break;
        case "thinking":
          if (activeThinkingIdx >= 0) {
            // Append to current thinking block
            const prev = middleEvents[activeThinkingIdx] as import("./types").ThinkingEvent;
            prev.content += chunk.content;
          } else {
            // Start a new thinking block
            activeThinkingIdx = middleEvents.length;
            middleEvents.push({
              type: "thinking",
              timestamp: chunk.timestamp,
              content: chunk.content,
            });
          }
          break;
        case "tool_call":
        case "tool_result":
          activeThinkingIdx = -1; // break the current thinking block
          middleEvents.push(chunk);
          break;
      }
    }

    // Build ordered event list
    const events: StreamEvent[] = [];
    if (userMessage) events.push(userMessage);
    events.push(...middleEvents);
    if (modelContent) {
      events.push({
        type: "text",
        role: "model",
        timestamp: modelTimestamp,
        content: modelContent,
      });
    }
    onChunk(events);
  }
}
