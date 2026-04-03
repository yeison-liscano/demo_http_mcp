import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import MessageBubble from "./MessageBubble";

interface MessageListProps {
  messages: ChatMessage[];
}

export default function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="message-list message-list--empty">
        <p>No messages yet. Ask me about vulnerabilities in any dependency!</p>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <MessageBubble key={`${msg.role}-${msg.timestamp}`} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
