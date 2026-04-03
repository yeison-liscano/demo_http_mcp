import { useCallback, useEffect, useState } from "react";
import { fetchChatHistory, sendChatMessage } from "../api";
import type { StreamEvent } from "../types";
import ChatInput from "./ChatInput";
import MessageList from "./MessageList";

export default function ChatApp() {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchChatHistory()
      .then((history) => setEvents(history))
      .catch((err) => {
        console.error("Failed to load chat history:", err);
        setError("Failed to load chat history.");
      });
  }, []);

  const handleSend = useCallback(async (prompt: string) => {
    setSending(true);
    setError(null);

    try {
      await sendChatMessage(prompt, (streamedEvents) => {
        setEvents((prev) => {
          const firstStreamed = streamedEvents[0];
          if (!firstStreamed || firstStreamed.type !== "text") return prev;

          const cutoff = prev.findIndex(
            (e) =>
              e.type === "text" && e.timestamp === firstStreamed.timestamp,
          );

          if (cutoff >= 0) {
            return [...prev.slice(0, cutoff), ...streamedEvents];
          }
          return [...prev, ...streamedEvents];
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

      <MessageList events={events} />

      {error && <div className="chat-app__error">{error}</div>}

      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}
