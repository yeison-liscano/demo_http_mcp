export interface ChatMessage {
  role: "user" | "model";
  timestamp: string;
  content: string;
}
