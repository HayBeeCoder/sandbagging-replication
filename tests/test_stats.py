"""The statistics must find real gaps, stay quiet without one, and be repeatable."""
import pytest

from sandbag.stats import bootstrap_interval, bootstrap_test, false_alarm_rate

LOW, HIGH, SAME = [0.4] * 50, [1.0] * 50, [0.8, 0.9, 1.0, 0.7, 0.9] * 10


def test_a_large_gap_is_significant():
    result = bootstrap_test(LOW, HIGH, resamples=5000)
    assert result["gap"] == pytest.approx(0.6) and result["p_one_sided"] < 0.001


def test_identical_groups_are_not_significant():
    result = bootstrap_test(SAME, SAME, resamples=5000)
    assert result["gap"] == 0 and result["p_one_sided"] > 0.4 and result["p_two_sided"] == 1.0


def test_a_gap_in_the_wrong_direction_is_not_evidence_of_sandbagging():
    result = bootstrap_test(HIGH, LOW, resamples=5000)  # better when a high score has consequences
    assert result["gap"] == pytest.approx(-0.6)
    assert result["p_one_sided"] > 0.99 and result["p_two_sided"] < 0.001


def test_the_same_seed_gives_the_same_answer():
    a, b = [0.5, 0.6, 0.7, 0.4] * 10, [0.6, 0.7, 0.8, 0.5] * 10
    assert bootstrap_test(a, b, 2000, seed=3) == bootstrap_test(a, b, 2000, seed=3)


def test_the_interval_contains_the_gap_and_is_ordered():
    a, b = [0.5, 0.6, 0.7, 0.4] * 10, [0.6, 0.7, 0.8, 0.5] * 10
    low, high = bootstrap_interval(a, b, resamples=5000)
    assert low < 0.1 < high and high - low < 0.3


def test_the_test_raises_a_false_alarm_about_one_time_in_a_hundred():
    assert 0.002 <= false_alarm_rate(alpha=0.01, experiments=1000, resamples=1000) <= 0.025


def test_a_real_gap_of_three_questions_is_almost_always_found():
    assert false_alarm_rate(true_gap=0.3, experiments=200, resamples=1000) > 0.95
