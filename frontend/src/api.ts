import type { ChatMessage } from "./types";

const API_BASE = "/api";

/** Shape of JSON lines from the streaming POST /chat/ endpoint. */
interface StreamedChunk {
  role: "user" | "model";
  content: string;
  timestamp: string;
  more_body?: boolean;
}

/**
 * Fetch existing chat history from the backend.
 * Returns parsed ChatMessage[] from newline-delimited JSON.
 */
export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const response = await fetch(`${API_BASE}/chat/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch chat history: ${response.status}`);
  }
  const text = await response.text();
  return text
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as ChatMessage);
}

/**
 * Send a chat prompt and stream back the response.
 * The backend streams text deltas — each line contains only the new fragment.
 * We accumulate model deltas into a single message before calling onChunk.
 */
export async function sendChatMessage(
  prompt: string,
  onChunk: (messages: ChatMessage[]) => void,
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
  let userMessage: ChatMessage | null = null;
  let modelContent = "";
  let modelTimestamp = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process all complete lines in the buffer
    const lines = buffer.split("\n");
    // Last element may be an incomplete line — keep it in the buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.trim().length === 0) continue;
      const chunk = JSON.parse(line) as StreamedChunk;

      if (chunk.role === "user") {
        userMessage = {
          role: "user",
          timestamp: chunk.timestamp,
          content: chunk.content,
        };
      } else {
        // Model deltas: accumulate content
        if (!modelTimestamp) modelTimestamp = chunk.timestamp;
        modelContent += chunk.content;
      }
    }

    // Build current message list and notify
    const messages: ChatMessage[] = [];
    if (userMessage) messages.push(userMessage);
    if (modelContent) {
      messages.push({
        role: "model",
        timestamp: modelTimestamp,
        content: modelContent,
      });
    }
    if (messages.length > 0) {
      onChunk(messages);
    }
  }
}
