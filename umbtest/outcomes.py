"""One place that maps tool results to pytest outcomes.

- not_supported: the tool does not offer this feature            -> skip
- known_issue:   a failure we tolerate for now (reported issue)  -> xfail
Everything else is judged by the test itself (exit code etc.).
"""

from __future__ import annotations

import pytest

from umbtest.tools import ReportedResults


def apply_tolerances(role: str, result: ReportedResults, known_issue: str | None = None) -> None:
    """Skip or xfail when `result` falls into a tolerated category.

    :param role: what the tool did, for the message (e.g. "Loader", "Storm reading")
    :param known_issue: a reason from outside the result (e.g. the regression manifest);
        it only counts if the run actually failed.
    """
    if result.known_issue is None and known_issue is not None and result.exit_code != 0:
        result.known_issue = known_issue
    if result.known_issue is not None and result.exit_code != 0:
        pytest.xfail(f"{role}: {result.known_issue}")
    if result.not_supported:
        pytest.skip(f"{role}: not supported")
