import type { ChatMessage } from "./types";

const API_BASE = "/api";

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
 * Calls `onChunk` with the full accumulated message list as each chunk arrives.
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
  let accumulated = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    accumulated += decoder.decode(value, { stream: true });

    const messages = accumulated
      .split("\n")
      .filter((line) => line.trim().length > 0)
      .map((line) => JSON.parse(line) as ChatMessage);

    onChunk(messages);
  }
}
