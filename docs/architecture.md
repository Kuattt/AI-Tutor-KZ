# Backend v1 architecture

```text
Client
  -> FastAPI API routes
  -> TutorService
       -> GuidedSolvingPolicy
       -> TutorSessionStore
       -> LLMProvider
            -> OllamaProvider
                 -> http://127.0.0.1:11434
```

The API layer validates HTTP input and formats JSON or SSE output. It does not
contain prompt logic or Ollama-specific code.

`TutorService` coordinates policy decisions, message history, model requests,
successful assistant-message persistence, disconnect handling, and generation
metrics. One generation is allowed at a time per session to avoid history
races.

`LLMProvider` is the model boundary. `OllamaProvider` is the only Backend v1
implementation and consumes Ollama's streaming NDJSON API directly with
`httpx.AsyncClient`. A future vLLM implementation can satisfy the same
interface without changing tutor or route code.

`TutorSessionStore` is the persistence boundary. The in-memory implementation
is intentionally suitable only for local Backend v1 development. It can later
be replaced by a PostgreSQL or Redis-backed store without changing API routes
or model integration.

The system prompt is rebuilt for each request and is never trimmed from model
context. Stored user/assistant history is bounded by
`TUTOR_MAX_HISTORY_MESSAGES`. Session state disappears on process restart; no
summarization is performed yet.

Inactive sessions have a configurable TTL. A lightweight task owned by the
FastAPI lifespan periodically asks the store to remove expired sessions. The
store atomically protects sessions with active generations, so cleanup cannot
delete in-flight state. The same lifespan cancels the cleanup task and closes
the provider HTTP client during shutdown.

## Guided-solving policy

The policy has three effective states:

- `direct_explanation`: explain concepts directly.
- `guided_solving`: provide one next step and resist early requests for a final
  answer.
- `answer_reveal_allowed`: confirm or reveal the result once essential
  reasoning is present.

The state machine is deliberately small and deterministic. The model receives a
mode-specific instruction in addition to the reliability baseline prompt.

## Streaming lifecycle

1. Validate the session before starting the HTTP stream.
2. Save the user message and policy state.
3. Emit `start`.
4. Forward real Ollama chunks as `delta` events.
5. On success, save the combined assistant response.
6. Emit `metadata` and `done`.
7. On mid-stream failure, emit `error` and do not save a partial assistant
   message.

During streaming, a low-frequency monitor uses Starlette's supported
`Request.is_disconnected()` check. Disconnecting closes the upstream
`httpx` response as soon as practical, records a cancellation, releases the
session lock, and never emits a misleading successful completion.

Operational metrics are concurrency-safe and remain in process memory. They
contain counts, timings, and token/character totals only—never message content.

