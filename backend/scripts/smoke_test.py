"""Real two-turn SSE smoke test against a running Backend v1 instance."""

import json
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx


BASE_URL = "http://127.0.0.1:8000"
FIRST_PROMPT = "Маған центрге тартқыш үдеуді қарапайым тілмен түсіндір."
SECOND_PROMPT = (
    "Егер жылдамдықты 2 есе арттырсақ, үдеу қалай өзгереді? "
    "Маған дайын жауапты бірден айтпа."
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class StreamResult:
    text: str
    first_token_seconds: float | None
    total_seconds: float
    event_names: list[str]
    finish_reason: str | None
    generated_tokens: int | None


def parse_event(block: str) -> tuple[str, dict] | None:
    event_name = ""
    data = ""
    for line in block.splitlines():
        if line.startswith("event: "):
            event_name = line[7:]
        elif line.startswith("data: "):
            data += line[6:]
    if not event_name or not data:
        return None
    return event_name, json.loads(data)


def stream_message(
    client: httpx.Client,
    session_id: str,
    message: str,
) -> StreamResult:
    started = time.perf_counter()
    first_token: float | None = None
    fragments: list[str] = []
    event_names: list[str] = []
    finish_reason: str | None = None
    generated_tokens: int | None = None
    buffer = ""
    with client.stream(
        "POST",
        f"/api/v1/tutor/sessions/{session_id}/messages",
        json={"message": message, "mode": "auto"},
    ) as response:
        response.raise_for_status()
        for text in response.iter_text():
            buffer += text.replace("\r\n", "\n")
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                parsed = parse_event(block)
                if parsed is None:
                    continue
                event, data = parsed
                event_names.append(event)
                if event == "delta":
                    if first_token is None:
                        first_token = time.perf_counter() - started
                    chunk = data["text"]
                    fragments.append(chunk)
                    print(chunk, end="", flush=True)
                elif event == "error":
                    raise RuntimeError(
                        f"Streaming error {data.get('code')}: {data.get('message')}"
                    )
                elif event == "metadata":
                    generated_tokens = data.get("generated_tokens")
                elif event == "done":
                    finish_reason = data.get("finish_reason")
    print()
    return StreamResult(
        text="".join(fragments),
        first_token_seconds=first_token,
        total_seconds=time.perf_counter() - started,
        event_names=event_names,
        finish_reason=finish_reason,
        generated_tokens=generated_tokens,
    )


def main() -> int:
    timeout = httpx.Timeout(connect=10.0, read=240.0, write=30.0, pool=10.0)
    with httpx.Client(base_url=BASE_URL, timeout=timeout) as client:
        app_health = client.get("/health")
        app_health.raise_for_status()
        ollama_health = client.get("/health/ollama")
        ollama_health.raise_for_status()
        print(f"Health: {app_health.json()} / {ollama_health.json()}")

        created = client.post(
            "/api/v1/tutor/sessions",
            json={"language": "mixed", "grade": 9},
        )
        created.raise_for_status()
        session_id = created.json()["session_id"]
        print(f"Session: {session_id}")

        print(f"\nStudent 1: {FIRST_PROMPT}\nTutor 1: ", end="", flush=True)
        first = stream_message(client, session_id, FIRST_PROMPT)

        print(f"\nStudent 2: {SECOND_PROMPT}\nTutor 2: ", end="", flush=True)
        second = stream_message(client, session_id, SECOND_PROMPT)

        session = client.get(f"/api/v1/tutor/sessions/{session_id}")
        session.raise_for_status()
        history = session.json()["messages"]
        context_retained = (
            len(history) == 4
            and history[0]["content"] == FIRST_PROMPT
            and history[1]["content"] == first.text.strip()
            and history[2]["content"] == SECOND_PROMPT
            and history[3]["content"] == second.text.strip()
        )
        progressive = (
            first.event_names.count("delta") > 1
            and second.event_names.count("delta") > 1
        )

        summary = {
            "session_id": session_id,
            "context_retained": context_retained,
            "progressive_streaming": progressive,
            "first": {
                "first_token_seconds": first.first_token_seconds,
                "total_seconds": first.total_seconds,
                "delta_events": first.event_names.count("delta"),
                "finish_reason": first.finish_reason,
                "generated_tokens": first.generated_tokens,
            },
            "second": {
                "first_token_seconds": second.first_token_seconds,
                "total_seconds": second.total_seconds,
                "delta_events": second.event_names.count("delta"),
                "finish_reason": second.finish_reason,
                "generated_tokens": second.generated_tokens,
            },
        }
        print("\nSMOKE_RESULT=" + json.dumps(summary, ensure_ascii=False))
        if not context_retained or not progressive:
            return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"\nSmoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
