from app.services.decision import NOOP, OPEN, RESOLVE, decide


def test_no_results_does_nothing():
    assert decide([], False, 3) == NOOP


def test_healthy_monitor_does_nothing():
    assert decide([True, True, True], False, 3) == NOOP


def test_single_failure_does_not_open_incident():
    assert decide([False, True, True], False, 3) == NOOP


def test_two_failures_below_threshold_do_nothing():
    assert decide([False, False, True], False, 3) == NOOP


def test_threshold_failures_open_incident():
    assert decide([False, False, False], False, 3) == OPEN


def test_not_enough_history_does_not_open_incident():
    assert decide([False, False], False, 3) == NOOP


def test_existing_incident_is_not_opened_twice():
    assert decide([False, False, False, False], True, 3) == NOOP


def test_recovery_resolves_open_incident():
    assert decide([True, False, False, False], True, 3) == RESOLVE


def test_success_without_incident_does_nothing():
    assert decide([True, False, False], False, 3) == NOOP


def test_threshold_of_one_opens_on_first_failure():
    assert decide([False], False, 1) == OPEN
