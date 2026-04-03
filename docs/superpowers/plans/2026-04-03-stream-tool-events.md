# Stream Tool Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream tool calls and tool results to the frontend as collapsible cards alongside text messages.

**Architecture:** Replace the single `ChatMessage` type with a discriminated `StreamEvent` union (`text | tool_call | tool_result`). Backend yields tool events from the agent loop. Frontend accumulates text deltas and appends tool events, rendering them as collapsible cards with loading states.

**Tech Stack:** Python/FastAPI/pydantic-ai (backend), React/TypeScript/Vite (frontend)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/agent.py` | Modify | Replace models with `StreamEvent` union, yield tool events from agent loop |
| `backend/app/app.py` | Modify | Add `type: "text"` to user prompt and history, update type annotations |
| `frontend/src/types.ts` | Modify | Replace `ChatMessage` with `StreamEvent` union types |
| `frontend/src/api.ts` | Modify | Parse by `type`, accumulate text, append tool events |
| `frontend/src/components/ChatApp.tsx` | Modify | State type → `StreamEvent[]` |
| `frontend/src/components/MessageList.tsx` | Modify | Render by event type, group tool cards by `tool_call_id` |
| `frontend/src/components/MessageBubble.tsx` | Modify | Accept `TextEvent` instead of `ChatMessage` |
| `frontend/src/components/ToolCard.tsx` | Create | Collapsible card for tool call + result |
| `frontend/src/App.css` | Modify | Add tool card styles |

---

### Task 1: Backend — Replace models and yield tool events

**Files:**
- Modify: `backend/app/agent.py`

- [ ] **Step 1: Replace models with StreamEvent union**

Replace the `ChatMessage`, `ToolExecutionRequest`, and `ToolExecutionResult` classes with:

```python
class TextEvent(BaseModel):
    """Text chunk streamed to the browser."""
    type: Literal["text"] = "text"
    role: Literal["user", "model"]
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    more_body: bool = True


class ToolCallEvent(BaseModel):
    """Emitted when the model invokes a tool."""
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    args: dict
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ToolResultEvent(BaseModel):
    """Emitted when a tool returns its result."""
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool_name: str
    args: dict
    result: Any
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


StreamEvent = TextEvent | ToolCallEvent | ToolResultEvent
```

Remove `ChatMessage`, `ToolExecutionRequest`, `ToolExecutionResult`, and `_build_tool_execution_result` (unused).

- [ ] **Step 2: Update `_process_model_response_stream_event` return type**

Change return type from `ChatMessage | None` to `TextEvent | None` and update the two return statements to use `TextEvent` instead of `ChatMessage`:

```python
def _process_model_response_stream_event(
    model_response_stream_event: ModelResponseStreamEvent,
) -> TextEvent | None:
    if isinstance(model_response_stream_event, PartStartEvent) and isinstance(
        model_response_stream_event.part,
        TextPart,
    ):
        return TextEvent(
            content=model_response_stream_event.part.content,
            more_body=True,
            role="model",
        )
    if isinstance(model_response_stream_event, PartDeltaEvent) and isinstance(
        model_response_stream_event.delta,
        TextPartDelta | ThinkingPartDelta,
    ):
        return TextEvent(
            content=model_response_stream_event.delta.content_delta or "",
            role="model",
            more_body=True,
        )
    return None
```

- [ ] **Step 3: Update `_process_handle_response_event` to return `StreamEvent`**

Change it to return `ToolCallEvent | ToolResultEvent | None`:

```python
def _process_handle_response_event(
    handle_response_event: HandleResponseEvent,
    called_tools: dict[str, ToolCallEvent],
) -> ToolCallEvent | ToolResultEvent | None:
    if isinstance(handle_response_event, FunctionToolResultEvent) and isinstance(
        handle_response_event.result,
        ToolReturnPart,
    ):
        tool_part = handle_response_event.result
        call = called_tools.get(tool_part.tool_call_id)
        return ToolResultEvent(
            tool_call_id=tool_part.tool_call_id,
            tool_name=tool_part.tool_name,
            args=call.args if call else {},
            result=tool_part.content,
        )
    if isinstance(handle_response_event, FunctionToolCallEvent):
        part = handle_response_event.part
        args: dict | None = None
        try:
            args = json.loads(part.args) if isinstance(part.args, str) else part.args
        except json.JSONDecodeError:
            args = {"args": part.args}
        if args is None:
            args = {}
        event = ToolCallEvent(
            tool_call_id=part.tool_call_id,
            tool_name=part.tool_name,
            args=args,
        )
        called_tools[event.tool_call_id] = event
        return event
    return None
```

Note: `called_tools` dict is passed in so tool results can look up original args.

- [ ] **Step 4: Update `_process_tool_events` to yield instead of print**

```python
async def _process_tool_events(
    handle_stream: AsyncIterable[HandleResponseEvent],
    called_tools: dict[str, ToolCallEvent],
) -> AsyncIterator[ToolCallEvent | ToolResultEvent]:
    async for event in handle_stream:
        tool_event = _process_handle_response_event(event, called_tools)
        if tool_event is None:
            continue
        yield tool_event
```

- [ ] **Step 5: Update `_process_model_events` return type**

```python
async def _process_model_events(
    request_stream: AsyncIterable[ModelResponseStreamEvent],
) -> AsyncIterator[TextEvent]:
    async for request_event in request_stream:
        processed_event = _process_model_response_stream_event(request_event)
        if processed_event is None:
            continue
        yield processed_event
```

- [ ] **Step 6: Update `_iterate_agent_nodes` to yield tool events and use `StreamEvent`**

```python
async def _iterate_agent_nodes(
    run: AgentRun[None, str],
    database: AgentMemory,
) -> AsyncIterator[StreamEvent]:
    called_tools: dict[str, ToolCallEvent] = {}
    async for node in run:
        if Agent.is_call_tools_node(node):
            async with node.stream(run.ctx) as handle_stream:
                async for tool_event in _process_tool_events(handle_stream, called_tools):
                    yield tool_event
            continue
        if Agent.is_model_request_node(node):
            async with node.stream(run.ctx) as request_stream:
                async for response in _process_model_events(request_stream):
                    yield response
            continue
        if Agent.is_end_node(node):
            yield TextEvent(role="model", content="\n\n")
            if run.result:
                await database.add_messages(run.result.new_messages_json())
```

- [ ] **Step 7: Update `stream_messages` return type and error handling**

```python
async def stream_messages(
    agent: Agent,
    prompt: str,
    database: AgentMemory,
) -> AsyncIterator[StreamEvent]:
    messages = await database.get_messages()
    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {os.getenv('NVD_API_KEY')}"},
        timeout=httpx.Timeout(60.0),
    )
    server = MCPServerStreamableHTTP(
        url="http://localhost:8000/mcp/",
        http_client=http_client,
        timeout=60,
    )
    async with (
        agent.iter(
            prompt,
            message_history=messages,
            toolsets=[server],
        ) as run,
    ):
        try:
            async for response in _iterate_agent_nodes(run, database):
                yield response
        except ModelHTTPError:
            LOGGER.exception("Error streaming messages")
            yield TextEvent(
                role="model",
                content="Error Streaming",
                more_body=False,
            )
            return
```

- [ ] **Step 8: Verify backend types pass mypy**

Run: `cd backend && uv run mypy app/agent.py`
Expected: `Success: no issues found`

- [ ] **Step 9: Commit**

```bash
git add backend/app/agent.py
git commit -m "feat: stream tool call and result events from agent loop"
```

---

### Task 2: Backend — Update app.py for new event types

**Files:**
- Modify: `backend/app/app.py`

- [ ] **Step 1: Add `type: "text"` to user prompt in `post_chat`**

In `_stream_messages`, update the user prompt dict:

```python
yield (
    json.dumps(
        {
            "type": "text",
            "role": "user",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "content": prompt,
        },
    ).encode("utf-8")
    + b"\n"
)
```

- [ ] **Step 2: Add `type: "text"` to history in `to_chat_message`**

Update the `ChatMessage` TypedDict and `to_chat_message` return dicts:

```python
class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    type: Literal["text"]
    role: Literal["user", "model"]
    timestamp: str
    content: str


def to_chat_message(m: ModelMessage) -> ChatMessage | None:
    if isinstance(m, ModelRequest):
        for req_part in m.parts:
            if isinstance(req_part, UserPromptPart):
                return {
                    "type": "text",
                    "role": "user",
                    "timestamp": req_part.timestamp.isoformat(),
                    "content": str(req_part.content),
                }
    elif isinstance(m, ModelResponse):
        for resp_part in m.parts:
            if isinstance(resp_part, TextPart):
                return {
                    "type": "text",
                    "role": "model",
                    "timestamp": m.timestamp.isoformat(),
                    "content": resp_part.content,
                }
    return None
```

- [ ] **Step 3: Verify backend types pass mypy**

Run: `cd backend && uv run mypy app/app.py`
Expected: `Success: no issues found`

- [ ] **Step 4: Commit**

```bash
git add backend/app/app.py
git commit -m "feat: add type discriminator to streamed and history messages"
```

---

### Task 3: Frontend — Update types and API layer

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Replace `ChatMessage` with `StreamEvent` union in `types.ts`**

```typescript
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
```

- [ ] **Step 2: Update `api.ts` — `fetchChatHistory` returns `TextEvent[]`**

```typescript
import type { TextEvent, StreamEvent } from "./types";

const API_BASE = "/api";

export async function fetchChatHistory(): Promise<TextEvent[]> {
  const response = await fetch(`${API_BASE}/chat/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch chat history: ${response.status}`);
  }
  const text = await response.text();
  return text
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as TextEvent);
}
```

- [ ] **Step 3: Update `api.ts` — `sendChatMessage` parses by event type**

```typescript
export async function sendChatMessage(
  prompt: string,
  onChunk: (events: StreamEvent[]) => void,
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
  let userMessage: TextEvent | null = null;
  let modelContent = "";
  let modelTimestamp = "";
  const toolEvents: (StreamEvent)[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.trim().length === 0) continue;
      const chunk = JSON.parse(line) as StreamEvent;

      switch (chunk.type) {
        case "text":
          if (chunk.role === "user") {
            userMessage = chunk;
          } else {
            if (!modelTimestamp) modelTimestamp = chunk.timestamp;
            modelContent += chunk.content;
          }
          break;
        case "tool_call":
        case "tool_result":
          toolEvents.push(chunk);
          break;
      }
    }

    // Build ordered event list
    const events: StreamEvent[] = [];
    if (userMessage) events.push(userMessage);
    // Interleave tool events and model text in stream order:
    // tool events go before the final model text
    events.push(...toolEvents);
    if (modelContent) {
      events.push({
        type: "text",
        role: "model",
        timestamp: modelTimestamp,
        content: modelContent,
      });
    }
    onChunk(events);
  }
}
```

- [ ] **Step 4: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (may have errors from components not yet updated — that's fine, we fix those in the next tasks)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat: add StreamEvent types and parse tool events in API layer"
```

---

### Task 4: Frontend — Update ChatApp and MessageBubble for new types

**Files:**
- Modify: `frontend/src/components/ChatApp.tsx`
- Modify: `frontend/src/components/MessageBubble.tsx`

- [ ] **Step 1: Update `ChatApp.tsx` to use `StreamEvent`**

```typescript
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
```

- [ ] **Step 2: Update `MessageBubble.tsx` to accept `TextEvent`**

```typescript
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
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChatApp.tsx frontend/src/components/MessageBubble.tsx
git commit -m "feat: update ChatApp and MessageBubble for StreamEvent types"
```

---

### Task 5: Frontend — Create ToolCard component

**Files:**
- Create: `frontend/src/components/ToolCard.tsx`

- [ ] **Step 1: Create `ToolCard.tsx`**

```tsx
import { useState } from "react";
import type { ToolCallEvent, ToolResultEvent } from "../types";

interface ToolCardProps {
  call: ToolCallEvent;
  result?: ToolResultEvent;
}

export default function ToolCard({ call, result }: ToolCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isLoading = !result;

  const argsSummary = Object.entries(call.args)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");

  return (
    <div className="tool-card">
      <button
        className="tool-card__header"
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <span className="tool-card__icon">
          {isLoading ? (
            <span className="tool-card__spinner" />
          ) : (
            <span className="tool-card__check">&#10003;</span>
          )}
        </span>
        <span className="tool-card__name">{call.tool_name}</span>
        <span className="tool-card__args-summary">({argsSummary})</span>
        <span
          className={`tool-card__chevron ${expanded ? "tool-card__chevron--open" : ""}`}
        >
          &#9656;
        </span>
      </button>

      {expanded && (
        <div className="tool-card__body">
          <div className="tool-card__section">
            <div className="tool-card__section-label">Arguments</div>
            <pre className="tool-card__json">
              {JSON.stringify(call.args, null, 2)}
            </pre>
          </div>
          {result && (
            <div className="tool-card__section">
              <div className="tool-card__section-label">Result</div>
              <pre className="tool-card__json">
                {JSON.stringify(result.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ToolCard.tsx
git commit -m "feat: add ToolCard collapsible component"
```

---

### Task 6: Frontend — Update MessageList to render tool cards

**Files:**
- Modify: `frontend/src/components/MessageList.tsx`

- [ ] **Step 1: Rewrite `MessageList.tsx` to dispatch by event type**

```tsx
import { useEffect, useRef } from "react";
import type { StreamEvent, ToolCallEvent, ToolResultEvent } from "../types";
import MessageBubble from "./MessageBubble";
import ToolCard from "./ToolCard";

interface MessageListProps {
  events: StreamEvent[];
}

export default function MessageList({ events }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  if (events.length === 0) {
    return (
      <div className="message-list message-list--empty">
        <p>No messages yet. Ask me about vulnerabilities in any dependency!</p>
      </div>
    );
  }

  // Build a map of tool_call_id → result for pairing
  const resultMap = new Map<string, ToolResultEvent>();
  for (const e of events) {
    if (e.type === "tool_result") {
      resultMap.set(e.tool_call_id, e);
    }
  }

  // Track which tool_call_ids we've already rendered
  const renderedToolCalls = new Set<string>();

  return (
    <div className="message-list">
      {events.map((event, i) => {
        if (event.type === "text") {
          return (
            <MessageBubble
              key={`text-${event.role}-${event.timestamp}`}
              message={event}
            />
          );
        }
        if (event.type === "tool_call") {
          renderedToolCalls.add(event.tool_call_id);
          return (
            <ToolCard
              key={`tool-${event.tool_call_id}`}
              call={event}
              result={resultMap.get(event.tool_call_id)}
            />
          );
        }
        // tool_result: skip if already rendered with its tool_call
        if (event.type === "tool_result") {
          if (renderedToolCalls.has(event.tool_call_id)) return null;
          // Orphan result (no call seen) — render standalone
          const syntheticCall: ToolCallEvent = {
            type: "tool_call",
            tool_call_id: event.tool_call_id,
            tool_name: event.tool_name,
            args: event.args,
            timestamp: event.timestamp,
          };
          return (
            <ToolCard
              key={`tool-${event.tool_call_id}-${i}`}
              call={syntheticCall}
              result={event}
            />
          );
        }
        return null;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/MessageList.tsx
git commit -m "feat: render tool cards in message list"
```

---

### Task 7: Frontend — Add tool card styles

**Files:**
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Append tool card CSS to `App.css`**

Add after the existing styles:

```css
/* ── Tool card ── */
.tool-card {
  margin-bottom: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fffbeb;
  overflow: hidden;
}

.tool-card__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.6rem 1rem;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.9rem;
  text-align: left;
  color: #4a5568;
}

.tool-card__header:hover {
  background: #fef3c7;
}

.tool-card__icon {
  flex-shrink: 0;
  width: 1.2rem;
  text-align: center;
}

.tool-card__spinner {
  display: inline-block;
  width: 0.9rem;
  height: 0.9rem;
  border: 2px solid #e2e8f0;
  border-top-color: #d69e2e;
  border-radius: 50%;
  animation: tool-spin 0.8s linear infinite;
}

@keyframes tool-spin {
  to { transform: rotate(360deg); }
}

.tool-card__check {
  color: #38a169;
  font-weight: bold;
}

.tool-card__name {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  font-weight: 600;
  color: #b7791f;
}

.tool-card__args-summary {
  color: #718096;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.tool-card__chevron {
  flex-shrink: 0;
  font-size: 0.75rem;
  transition: transform 0.2s;
  color: #a0aec0;
}

.tool-card__chevron--open {
  transform: rotate(90deg);
}

.tool-card__body {
  border-top: 1px solid #e2e8f0;
  padding: 0.75rem 1rem;
}

.tool-card__section {
  margin-bottom: 0.75rem;
}

.tool-card__section:last-child {
  margin-bottom: 0;
}

.tool-card__section-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #718096;
  margin-bottom: 0.35rem;
}

.tool-card__json {
  background: #1a202c;
  color: #e2e8f0;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.8rem;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  margin: 0;
  max-height: 300px;
  overflow-y: auto;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.css
git commit -m "feat: add tool card styles"
```

---

### Task 8: Build and verify

- [ ] **Step 1: Run mypy on backend**

Run: `cd backend && uv run mypy app/agent.py app/app.py`
Expected: `Success: no issues found`

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Fix any issues found, then commit**

```bash
git add -A
git commit -m "fix: address build issues"
```

(Skip this step if no issues.)

- [ ] **Step 4: Final commit if not already committed**

```bash
git add -A
git commit -m "feat: stream tool calls and results to frontend as collapsible cards"
```
