import Markdown from "react-markdown";
import type { TextEvent } from "../types";

interface MessageBubbleProps {
  message: TextEvent;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`message ${isUser ? "message--user" : "message--model"}`}>
      <div className="message__label">{isUser ? "You" : "AI"}</div>
      <div className="message__content">
        <Markdown>{message.content}</Markdown>
      </div>
      <time className="message__time">
        {new Date(message.timestamp).toLocaleTimeString()}
      </time>
    </div>
  );
}
