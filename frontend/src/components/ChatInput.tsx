import { useState, type FormEvent } from "react";

interface ChatInputProps {
  onSend: (prompt: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [prompt, setPrompt] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setPrompt("");
  };

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <input
        type="text"
        className="chat-input__field"
        placeholder="Type your message..."
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        disabled={disabled}
        autoFocus
      />
      <button
        type="submit"
        className="chat-input__button"
        disabled={disabled || !prompt.trim()}
      >
        {disabled ? "Sending..." : "Send"}
      </button>
    </form>
  );
}
