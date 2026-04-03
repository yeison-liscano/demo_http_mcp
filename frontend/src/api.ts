import type { TextEvent, StreamEvent } from "./types";

const API_BASE = "/api";

export async function fetchChatHistory(): Promise<TextEvent[]> {
  const response = await fetch(`${API_BASE}/chat/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch chat history: ${response.status}`);
  }
  const text = await response.text();
  return text
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as TextEvent);
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
  let userMessage: TextEvent | null = null;
  let modelContent = "";
  let modelTimestamp = "";
  const toolEvents: StreamEvent[] = [];

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
        case "tool_call":
        case "tool_result":
          toolEvents.push(chunk);
          break;
      }
    }

    // Build ordered event list
    const events: StreamEvent[] = [];
    if (userMessage) events.push(userMessage);
    // Tool events go before the final model text
    events.push(...toolEvents);
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
