import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TutorMode(StrEnum):
    AUTO = "auto"
    DIRECT_EXPLANATION = "direct_explanation"
    GUIDED_SOLVING = "guided_solving"
    ANSWER_REVEAL_ALLOWED = "answer_reveal_allowed"


GUIDED_PATTERNS = (
    r"не\s+(?:говори|давай|показывай).{0,25}(?:ответ|решение|итог)",
    r"без\s+(?:ответа|готового\s+ответа)",
    r"(?:дай|давай|нужна|только).{0,15}(?:подсказ|нам[её]к)",
    r"решить\s+(?:сам|самой|самому|вместе)",
    r"жауапты.{0,20}(?:айтпа|бірден\s+айтпа)",
    r"(?:ишара|көмек).{0,20}(?:бер|керек)",
    r"өзім.{0,20}(?:шығар|шеш)",
)

EXPLANATION_PATTERNS = (
    r"(?:объясни|объясните|что\s+такое|как\s+работает|почему)",
    r"(?:түсіндір|дегеніміз\s+не|қалай\s+жұмыс|неліктен|не\s+үшін)",
)

REVEAL_REQUEST_PATTERNS = (
    r"(?:проверь|верно|правильно|подтверди).{0,20}(?:ответ|получил|получила)?",
    r"(?:аяқта|тексер|дұрыс\s+па|раста)",
    r"(?:что|чему).{0,15}(?:получится|равно)",
)

ESSENTIAL_REASONING_PATTERNS = (
    r"[a-zа-яәіңғүұқөһ]\s*(?:²|\^2)?\s*=\s*-?\d+(?:[,.]\d+)?",
    r"\d+\s*[-+×x*/:]\s*\d+\s*=\s*-?\d+",
    r"(?:получил|получила|наш[её]л|таптым|алдым).{0,25}-?\d+",
    r"(?:формула|формуласы).{0,30}[=/]",
)

FINAL_ANSWER_PATTERNS = (
    r"(?<![\w\d])(?:x|y|c|a|v|s)\s*=\s*-?\d+(?:[,.]\d+)?",
    r"(?:ответ|жауап)\s*[:=]?\s*-?\d+(?:[,.]\d+)?",
)

COMPLETION_REQUEST_PATTERNS = (
    r"(?:аяқта|заверши|закончи)",
    r"(?:чему|неге|нешеге).{0,20}(?:равен|тең)",
)


@dataclass(frozen=True)
class PolicyDecision:
    mode: TutorMode
    guided_steps: int
    reason: str


class GuidedSolvingPolicy:
    @staticmethod
    def _matches(message: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, message, re.I | re.U) for pattern in patterns)

    def decide(
        self,
        message: str,
        requested_mode: TutorMode,
        current_mode: TutorMode,
        metadata: dict[str, Any],
    ) -> PolicyDecision:
        guided_steps = int(metadata.get("guided_steps", 0))
        has_reasoning = self._matches(message, ESSENTIAL_REASONING_PATTERNS)
        asks_reveal = self._matches(message, REVEAL_REQUEST_PATTERNS)
        has_final_answer = self._matches(message, FINAL_ANSWER_PATTERNS)
        asks_completion = self._matches(message, COMPLETION_REQUEST_PATTERNS)
        reveal_ready = has_final_answer or (
            has_reasoning and asks_completion
        )

        if requested_mode == TutorMode.DIRECT_EXPLANATION:
            return PolicyDecision(requested_mode, 0, "explicit direct mode")
        if requested_mode == TutorMode.ANSWER_REVEAL_ALLOWED:
            return PolicyDecision(requested_mode, guided_steps, "explicit reveal mode")
        if requested_mode == TutorMode.GUIDED_SOLVING:
            if reveal_ready and (asks_reveal or asks_completion):
                return PolicyDecision(
                    TutorMode.ANSWER_REVEAL_ALLOWED,
                    guided_steps + 1,
                    "essential reasoning completed",
                )
            return PolicyDecision(
                TutorMode.GUIDED_SOLVING,
                guided_steps + 1,
                "explicit guided mode",
            )

        if self._matches(message, GUIDED_PATTERNS):
            return PolicyDecision(
                TutorMode.GUIDED_SOLVING,
                max(1, guided_steps + 1),
                "student requested guided solving",
            )

        if current_mode == TutorMode.GUIDED_SOLVING:
            next_steps = guided_steps + (1 if has_reasoning else 0)
            if reveal_ready and (asks_reveal or asks_completion):
                return PolicyDecision(
                    TutorMode.ANSWER_REVEAL_ALLOWED,
                    next_steps,
                    "guided reasoning is sufficient",
                )
            return PolicyDecision(
                TutorMode.GUIDED_SOLVING,
                next_steps,
                "guided session continues",
            )

        if current_mode == TutorMode.ANSWER_REVEAL_ALLOWED and has_reasoning:
            return PolicyDecision(
                TutorMode.ANSWER_REVEAL_ALLOWED,
                guided_steps,
                "answer reveal remains appropriate",
            )

        if self._matches(message, EXPLANATION_PATTERNS):
            return PolicyDecision(
                TutorMode.DIRECT_EXPLANATION,
                0,
                "student requested an explanation",
            )

        return PolicyDecision(
            TutorMode.DIRECT_EXPLANATION,
            0,
            "default direct explanation",
        )

