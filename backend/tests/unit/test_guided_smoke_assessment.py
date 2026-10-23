from scripts.guided_policy_smoke import TurnResult, assess


def turn(response: str) -> TurnResult:
    return TurnResult(
        prompt="",
        response=response,
        first_token_seconds=1.0,
        total_seconds=2.0,
        delta_events=1,
        finish_reason="stop",
        generated_tokens=10,
    )


def test_assessment_accepts_natural_correction_and_division_guidance() -> None:
    result = assess(
        [
            turn("Сначала уберём 5. Что сделаешь с обеими частями?"),
            turn("20 - 5 = 15, а не 25. Теперь у нас 3x = 15."),
            turn(
                "Нужно разделить обе части на коэффициент при переменной, "
                "то есть на 3. Выполни деление самостоятельно."
            ),
            turn("Проверка верна: x = 5 — правильный ответ."),
        ]
    )

    assert result == {
        "incorrect_claim_rejected": True,
        "incorrect_confirmation": False,
        "early_answer_leak": False,
        "division_guidance": True,
        "final_answer_confirmed": True,
        "successful": True,
    }


def test_assessment_rejects_praise_and_early_answer_leak() -> None:
    result = assess(
        [
            turn("Сразу получаем x = 5."),
            turn("Ты абсолютно прав!"),
            turn("Подумай о следующем действии."),
            turn("Ответ x = 5."),
        ]
    )

    assert result["incorrect_claim_rejected"] is False
    assert result["incorrect_confirmation"] is True
    assert result["early_answer_leak"] is True
    assert result["division_guidance"] is False
    assert result["successful"] is False
