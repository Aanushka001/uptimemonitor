"""Pure incident decision logic. No database, no network: easy to test."""

OPEN = "OPEN"
RESOLVE = "RESOLVE"
NOOP = "NOOP"


def decide(recent_results: list[bool], has_open_incident: bool, threshold: int) -> str:
    """Decide what to do after a new check result was stored.

    recent_results: outcomes of the latest checks, newest first (True = success).
    has_open_incident: whether the monitor already has an unresolved incident.
    threshold: consecutive failures required before an incident is opened.
    """
    if not recent_results:
        return NOOP

    if recent_results[0]:
        return RESOLVE if has_open_incident else NOOP

    window = recent_results[:threshold]
    threshold_reached = len(window) == threshold and not any(window)
    if threshold_reached and not has_open_incident:
        return OPEN
    return NOOP
