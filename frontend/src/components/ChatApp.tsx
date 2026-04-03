import { useCallback, useEffect, useState } from "react";
import { fetchChatHistory, sendChatMessage } from "../api";
import type { ChatMessage } from "../types";
import ChatInput from "./ChatInput";
import MessageList from "./MessageList";

export default function ChatApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load chat history on mount
  useEffect(() => {
    fetchChatHistory()
      .then(setMessages)
      .catch((err) => {
        console.error("Failed to load chat history:", err);
        setError("Failed to load chat history.");
      });
  }, []);

  const handleSend = useCallback(async (prompt: string) => {
    setSending(true);
    setError(null);

    try {
      await sendChatMessage(prompt, (streamedMessages) => {
        // Replace messages from the current response stream
        // We keep existing history and append the new streamed messages
        setMessages((prev) => {
          // Find where the new messages start (by matching the user prompt timestamp)
          // The first streamed message is always the user prompt
          const firstStreamedTimestamp = streamedMessages[0]?.timestamp;
          if (!firstStreamedTimestamp) return prev;

          const cutoff = prev.findIndex(
            (m) => m.timestamp === firstStreamedTimestamp,
          );

          if (cutoff >= 0) {
            // Replace from the cutoff point with streamed data
            return [...prev.slice(0, cutoff), ...streamedMessages];
          }

          // New messages, append to existing
          return [...prev, ...streamedMessages];
        });
      });
    } catch (err) {
      console.error("Failed to send message:", err);
      setError("Failed to send message. Check the console for details.");
    } finally {
      setSending(false);
    }
  }, []);

  return (
    <div className="chat-app">
      <header className="chat-app__header">
        <h1>Vulnerability Agent</h1>
        <p>Ask me about vulnerabilities in any dependency</p>
      </header>

      <MessageList messages={messages} />

      {error && <div className="chat-app__error">{error}</div>}

      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}
