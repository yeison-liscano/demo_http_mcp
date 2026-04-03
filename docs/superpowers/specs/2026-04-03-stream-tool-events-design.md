# Stream Tool Calls & Results to Frontend

## Problem

The chat UI only displays text responses. When the agent calls tools (e.g. `search_cpe`, `search_cve`), the user sees nothing until the final text response arrives. Tool calls and results should be visible as collapsible cards in the chat stream.

## Stream Protocol

Currently the backend streams only text deltas as JSON lines. We introduce a discriminated union via a `type` field on every streamed line:

| `type` | Fields | When emitted |
|--------|--------|--------------|
| `"text"` | `role`, `content`, `timestamp`, `more_body` | Model text delta (existing behavior) |
| `"tool_call"` | `tool_call_id`, `tool_name`, `args`, `timestamp` | Model invokes a tool |
| `"tool_result"` | `tool_call_id`, `tool_name`, `args`, `result`, `timestamp` | Tool execution completes |

The user prompt line (first line in the stream, emitted by `app.py`) gains `"type": "text"` to match.

The `tool_call_id` links a call to its result. A `tool_call` always arrives before its corresponding `tool_result`.

## Backend Changes

### `agent.py`

**Models**: Replace `ChatMessage`, `ToolExecutionRequest`, `ToolExecutionResult` with a unified set:

```python
class TextEvent(BaseModel):
    type: Literal["text"] = "text"
    role: Literal["user", "model"]
    content: str
    timestamp: str = Field(default_factory=...)
    more_body: bool = True

class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    args: dict
    timestamp: str = Field(default_factory=...)

class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool_name: str
    args: dict
    result: Any
    timestamp: str = Field(default_factory=...)

StreamEvent = TextEvent | ToolCallEvent | ToolResultEvent
```

**`_iterate_agent_nodes`**: The `call_tools_node` branch currently calls `_process_tool_events` which only `print()`s. Change it to `yield` `ToolCallEvent` and `ToolResultEvent` items instead. Track called tools in a dict so results include the original args.

**`stream_messages`**: Return type changes from `AsyncIterator[ChatMessage]` to `AsyncIterator[StreamEvent]`.

### `app.py`

**`post_chat`**: The user prompt line gains `"type": "text"`. The streaming loop calls `.model_dump_json()` on each `StreamEvent` (unchanged mechanically).

**`get_chat`**: The history endpoint returns `TextEvent`-shaped dicts (add `"type": "text"` to each). No tool events in history — they are ephemeral.

## Frontend Changes

### `types.ts`

```typescript
interface TextEvent {
  type: "text";
  role: "user" | "model";
  content: string;
  timestamp: string;
}

interface ToolCallEvent {
  type: "tool_call";
  tool_call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  timestamp: string;
}

interface ToolResultEvent {
  type: "tool_result";
  tool_call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  result: unknown;
  timestamp: string;
}

type StreamEvent = TextEvent | ToolCallEvent | ToolResultEvent;
```

`ChatMessage` is removed; replaced by `TextEvent`.

### `api.ts`

- `fetchChatHistory()`: Returns `TextEvent[]` (history lines now include `type: "text"`).
- `sendChatMessage()`: Parses each JSON line and dispatches by `type`:
  - `"text"` with `role: "user"` → stored as user message
  - `"text"` with `role: "model"` → content accumulated into a single model message (existing delta logic)
  - `"tool_call"` → appended as a distinct event
  - `"tool_result"` → appended as a distinct event
- `onChunk` receives `StreamEvent[]` — the ordered list of all events so far.

### `ChatApp.tsx`

- State type changes from `ChatMessage[]` to `StreamEvent[]`.
- `handleSend` and `fetchChatHistory` work with `StreamEvent[]`.
- Passes events to `MessageList`.

### `MessageList.tsx`

- Iterates `StreamEvent[]` instead of `ChatMessage[]`.
- Renders `MessageBubble` for `TextEvent`, `ToolCard` for tool events.
- For tool events: groups `tool_call` + `tool_result` by `tool_call_id`. If only `tool_call` exists (no result yet), renders the card in loading state.
- Key: uses `type-timestamp` for text events, `tool_call_id` for tool cards.

### `ToolCard.tsx` (new component)

A collapsible card showing:

**Header** (always visible):
- Tool icon/indicator
- Tool name (e.g. `search_cpe`)
- Args summary (e.g. `product=axios, version=1.14.1`)
- Loading spinner (if result not yet received)
- Chevron toggle for expand/collapse

**Body** (collapsed by default, toggleable):
- Full args as formatted JSON
- Result as formatted JSON (when available)

**States**:
- **Loading**: card visible with tool name + args + spinner. No result section.
- **Complete**: spinner replaced with checkmark. Result section available, collapsed by default.

### `App.css`

New styles for `.tool-card`, `.tool-card__header`, `.tool-card__body`, `.tool-card__spinner`, `.tool-card__chevron`. Visual style: muted border, slightly different background from message bubbles (e.g. light yellow/amber tint), monospace for args/result JSON.

## Data Flow

```
User sends prompt
  → Backend yields: {"type":"text","role":"user",...}
  → Model streams text: {"type":"text","role":"model","content":"I'll check...",...}
  → Model calls tool: {"type":"tool_call","tool_call_id":"abc","tool_name":"search_cpe","args":{...},...}
    → Frontend immediately shows ToolCard with spinner
  → Tool returns: {"type":"tool_result","tool_call_id":"abc","tool_name":"search_cpe","args":{...},"result":{...},...}
    → Frontend updates ToolCard: spinner → checkmark, result available
  → Model streams more text: {"type":"text","role":"model","content":"Found 2 vulnerabilities...",...}
  → End node: {"type":"text","role":"model","content":"\n\n",...}
```

## Files Changed

| File | Action |
|------|--------|
| `backend/app/agent.py` | Replace models, update `_iterate_agent_nodes` to yield tool events |
| `backend/app/app.py` | Add `type: "text"` to user prompt and history, update type annotations |
| `frontend/src/types.ts` | Replace `ChatMessage` with `StreamEvent` union |
| `frontend/src/api.ts` | Parse by `type`, accumulate text, append tool events |
| `frontend/src/components/ChatApp.tsx` | State type → `StreamEvent[]` |
| `frontend/src/components/MessageList.tsx` | Render by event type, group tool cards |
| `frontend/src/components/ToolCard.tsx` | New: collapsible card component |
| `frontend/src/components/MessageBubble.tsx` | Accept `TextEvent` instead of `ChatMessage` |
| `frontend/src/App.css` | Add tool card styles |
