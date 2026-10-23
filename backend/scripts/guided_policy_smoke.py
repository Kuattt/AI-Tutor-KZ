"""Repeated real-model guided-solving smoke test for Backend v1.1."""

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


PROMPTS = [
    "Помоги решить 3x+5=20, но не говори ответ сразу. Давай по одному шагу.",
    "Я вычел 5 и получил 3x=25. Правильно?",
    "Теперь 3x=15. Что дальше? Не говори итог сразу.",
    "Я разделил и получил x=5. Проверь.",
]


@dataclass
class TurnResult:
    prompt: str
    response: str
    first_token_seconds: float | None
    total_seconds: float
    delta_events: int
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
    prompt: str,
) -> TurnResult:
    started = time.perf_counter()
    first_token: float | None = None
    fragments: list[str] = []
    delta_events = 0
    finish_reason: str | None = None
    generated_tokens: int | None = None
    buffer = ""
    with client.stream(
        "POST",
        f"/api/v1/tutor/sessions/{session_id}/messages",
        json={"message": prompt, "mode": "auto"},
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
                if event == "delta":
                    if first_token is None:
                        first_token = time.perf_counter() - started
                    fragments.append(data["text"])
                    delta_events += 1
                elif event == "metadata":
                    generated_tokens = data.get("generated_tokens")
                elif event == "done":
                    finish_reason = data.get("finish_reason")
                elif event == "error":
                    raise RuntimeError(
                        f"{data.get('code')}: {data.get('message')}"
                    )
    return TurnResult(
        prompt=prompt,
        response="".join(fragments).strip(),
        first_token_seconds=first_token,
        total_seconds=time.perf_counter() - started,
        delta_events=delta_events,
        finish_reason=finish_reason,
        generated_tokens=generated_tokens,
    )


def assess(turns: list[TurnResult]) -> dict[str, bool]:
    correction = turns[1].response.casefold()
    strong_praise = bool(
        re.search(
            r"\b(?:ты\s+(?:абсолютно\s+)?прав|абсолютно\s+верно|вс[её]\s+правильно|молодец)\b",
            correction,
        )
    )
    correction_signal = bool(
        re.search(r"\b(?:нет|невер|неправиль|ошиб|қате|дұрыс\s+емес)\w*", correction)
    )
    has_fifteen = bool(re.search(r"3x\s*=\s*15|\b15\b", correction))
    contrast_rejection = bool(
        re.search(r"\b15\b.{0,30}(?:а\s+)?не\s+\$?25\b", correction)
        or re.search(r"\b20\s*-\s*5\s*(?:\\neq|!=|≠)\s*25\b", correction)
    )
    incorrect_confirmation = strong_praise and not correction_signal
    incorrect_claim_rejected = (
        has_fifteen
        and (correction_signal or contrast_rejection)
        and not incorrect_confirmation
    )

    pre_final = "\n".join(turn.response for turn in turns[:3])
    early_answer_leak = bool(
        re.search(r"\bx\s*=\s*5\b", pre_final, re.I | re.U)
    )
    division_guidance = bool(
        re.search(
            r"(?:раздел\w*.{0,120}\b3\b|дел\w*.{0,60}\b3\b|3-ке\s+бөл)",
            turns[2].response,
            re.I | re.U | re.S,
        )
    )
    final_text = turns[3].response
    final_answer_confirmed = bool(
        re.search(r"\bx\s*=\s*5\b", final_text, re.I | re.U)
        and re.search(
            r"(?:верн|правиль|дұрыс|да\b|иә\b|провер)",
            final_text,
            re.I | re.U,
        )
    )
    return {
        "incorrect_claim_rejected": incorrect_claim_rejected,
        "incorrect_confirmation": incorrect_confirmation,
        "early_answer_leak": early_answer_leak,
        "division_guidance": division_guidance,
        "final_answer_confirmed": final_answer_confirmed,
        "successful": (
            incorrect_claim_rejected
            and not incorrect_confirmation
            and not early_answer_leak
            and division_guidance
            and final_answer_confirmed
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    timeout = httpx.Timeout(connect=10.0, read=240.0, write=30.0, pool=10.0)
    run_results: list[dict] = []
    all_first_tokens: list[float] = []
    all_durations: list[float] = []

    with httpx.Client(base_url=args.base_url, timeout=timeout) as client:
        client.get("/health").raise_for_status()
        provider_health = client.get("/health/ollama")
        provider_health.raise_for_status()
        print(f"Provider: {provider_health.json()}")

        for run_number in range(1, args.runs + 1):
            created = client.post(
                "/api/v1/tutor/sessions",
                json={"language": "ru", "grade": 8},
            )
            created.raise_for_status()
            session_id = created.json()["session_id"]
            print(f"\nRun {run_number}/{args.runs} session={session_id}")

            turns: list[TurnResult] = []
            for turn_number, prompt in enumerate(PROMPTS, start=1):
                turn = stream_message(client, session_id, prompt)
                turns.append(turn)
                first_token_display = (
                    f"{turn.first_token_seconds:.3f}s"
                    if turn.first_token_seconds is not None
                    else "n/a"
                )
                print(
                    f"  turn {turn_number}: first={first_token_display} "
                    f"total={turn.total_seconds:.3f}s tokens={turn.generated_tokens}"
                )
                print(f"    {turn.response}")
                if turn.first_token_seconds is not None:
                    all_first_tokens.append(turn.first_token_seconds)
                all_durations.append(turn.total_seconds)

            checks = assess(turns)
            run_results.append(
                {
                    "run": run_number,
                    "session_id": session_id,
                    "turns": [asdict(turn) for turn in turns],
                    **checks,
                }
            )
            print(f"  checks={checks}")

    summary = {
        "runs": args.runs,
        "successful_guided_runs": sum(
            result["successful"] for result in run_results
        ),
        "incorrect_confirmations": sum(
            result["incorrect_confirmation"] for result in run_results
        ),
        "early_answer_leaks": sum(
            result["early_answer_leak"] for result in run_results
        ),
        "final_confirmations": sum(
            result["final_answer_confirmed"] for result in run_results
        ),
        "average_first_token_seconds": (
            round(statistics.fmean(all_first_tokens), 3)
            if all_first_tokens
            else None
        ),
        "average_total_seconds": round(
            statistics.fmean(all_durations), 3
        ),
    }
    report = {
        "suite": "Backend v1.1 guided-solving smoke",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_url": args.base_url,
        "model": provider_health.json().get("model"),
        "prompts": PROMPTS,
        "summary": summary,
        "results": run_results,
    }
    output_dir = Path(__file__).resolve().parents[1] / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"backend_v1_1_guided_smoke_{timestamp}.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\nSUMMARY=" + json.dumps(summary, ensure_ascii=False))
    print(f"REPORT={output_path}")
    return 0 if summary["successful_guided_runs"] == args.runs else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"Guided smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
