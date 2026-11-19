import pytest

from skills.clarification.priority import MissingDetail, select_questions

format_detail = MissingDetail("Формат", "Какой формат на выходе?", 2, 2, 2)
order_detail = MissingDetail("Порядок", "Как сортировать строки?", 2, 1, 1)
key_detail = MissingDetail("Ключ", "Какие записи считать дублями?", 3, 3, 1)
access_detail = MissingDetail("Доступ", "Кто может читать результат?", 1, 0, 1, security=True)


def test_formula_and_threshold():
    assert format_detail.priority == 8
    assert format_detail.needs_question()
    assert not order_detail.needs_question()
    assert select_questions([order_detail], threshold=7) == [order_detail]


def test_questions_ranked_and_security_included_below_threshold():
    assert select_questions([access_detail, order_detail, format_detail, key_detail]) == [
        key_detail, format_detail, access_detail,
    ]


@pytest.mark.parametrize(("asked", "expected"), [(0, 3), (3, 2), (5, 0), (6, 0)])
def test_default_question_budgets(asked, expected):
    details = [format_detail, order_detail, key_detail, access_detail]
    assert len(select_questions(details, threshold=0, already_asked=asked)) == expected


def test_configured_limits():
    assert select_questions([format_detail, key_detail], max_questions=1) == [key_detail]
    assert select_questions([key_detail], already_asked=1, max_total=1) == []


@pytest.mark.parametrize("score", [-1, 4, 1.5, True])
def test_scores_must_be_integers_on_scale(score):
    with pytest.raises(ValueError):
        MissingDetail("Формат", "Какой формат?", score, 0, 0)
