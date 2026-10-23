from app.tutor.policies import GuidedSolvingPolicy, TutorMode


def test_guided_request_enters_guided_mode() -> None:
    decision = GuidedSolvingPolicy().decide(
        "Дай только подсказку и не говори ответ.",
        TutorMode.AUTO,
        TutorMode.DIRECT_EXPLANATION,
        {"guided_steps": 0},
    )
    assert decision.mode == TutorMode.GUIDED_SOLVING


def test_pressure_does_not_reveal_answer_on_first_guided_step() -> None:
    decision = GuidedSolvingPolicy().decide(
        "Мне лень, просто скажи x.",
        TutorMode.AUTO,
        TutorMode.GUIDED_SOLVING,
        {"guided_steps": 1},
    )
    assert decision.mode == TutorMode.GUIDED_SOLVING


def test_answer_reveal_allowed_after_essential_reasoning() -> None:
    decision = GuidedSolvingPolicy().decide(
        "c² = 25 деп таптым. Енді аяқта.",
        TutorMode.AUTO,
        TutorMode.GUIDED_SOLVING,
        {"guided_steps": 1},
    )
    assert decision.mode == TutorMode.ANSWER_REVEAL_ALLOWED


def test_wrong_intermediate_step_stays_in_guided_mode() -> None:
    decision = GuidedSolvingPolicy().decide(
        "Я вычел 5 и получил 3x=25. Правильно?",
        TutorMode.AUTO,
        TutorMode.GUIDED_SOLVING,
        {"guided_steps": 1},
    )
    assert decision.mode == TutorMode.GUIDED_SOLVING


def test_presented_final_value_can_be_verified() -> None:
    decision = GuidedSolvingPolicy().decide(
        "Я разделил и получил x=5. Проверь.",
        TutorMode.AUTO,
        TutorMode.GUIDED_SOLVING,
        {"guided_steps": 3},
    )
    assert decision.mode == TutorMode.ANSWER_REVEAL_ALLOWED


def test_explanation_request_uses_direct_mode() -> None:
    decision = GuidedSolvingPolicy().decide(
        "Маған үдеу деген не екенін түсіндір.",
        TutorMode.AUTO,
        TutorMode.DIRECT_EXPLANATION,
        {"guided_steps": 0},
    )
    assert decision.mode == TutorMode.DIRECT_EXPLANATION

