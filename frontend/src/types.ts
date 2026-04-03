export interface TextEvent {
  type: "text";
  role: "user" | "model";
  content: string;
  timestamp: string;
}

export interface ToolCallEvent {
  type: "tool_call";
  tool_call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  timestamp: string;
}

export interface ToolResultEvent {
  type: "tool_result";
  tool_call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  result: unknown;
  timestamp: string;
}

export type StreamEvent = TextEvent | ToolCallEvent | ToolResultEvent;
