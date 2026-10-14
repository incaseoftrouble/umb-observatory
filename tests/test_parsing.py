from pathlib import Path
from typing import cast

from umbtest.tools import (
    ModestCLI,
    PrismCLI,
    ReportedResults,
    StormCLI,
    contains_any_of,
    parse_logfile_prism,
    parse_logfile_storm,
    try_parse,
)

FIXTURES = Path(__file__).parent / "fixtures" / "logs"


def _inv(logfile: str) -> ReportedResults:
    inv = ReportedResults()
    inv.exit_code = 1
    return inv


def test_try_parse_returns_value_and_advances_position():
    result: dict[str, int] = {}
    pos = try_parse("a=42;\nb", 0, "a=", ";", result, "x", int)
    assert result["x"] == 42
    assert pos == 5


def test_try_parse_missing_keeps_position():
    result: dict[str, int] = {}
    pos = try_parse("foobar", 0, "missing", "\n", result, "x", int)
    assert "x" not in result
    assert pos == 0


def test_try_parse_resumes_after_previous_hit():
    result: dict[str, int | float] = {}
    log = "Time for model construction: 0.004s.\nStates: \t4\n"
    pos = try_parse(log, 0, "Time for model construction: ", "s.", result, "t", float)
    pos = try_parse(log, pos, "States: \t", "\n", result, "states", int)
    assert result == {"t": 0.004, "states": 4}
    assert pos == len(log)


def test_contains_any_of():
    assert contains_any_of("one two three", ["two", "four"])
    assert not contains_any_of("one two three", ["four", "five"])


def test_parse_storm_success(fixture_log: str = "storm_success.log") -> None:
    inv = _inv(fixture_log)
    parse_logfile_storm((FIXTURES / "storm_success.log").read_text(), inv)
    result = inv
    info = result.model_info
    assert info is not None
    model_building_time: float = cast(float, info["model-building-time"])
    assert abs(model_building_time - 0.004) < 1e-6
    assert info["states"] == 4
    assert info["transitions"] == 10
    assert info["choices"] == 7
    assert result.not_supported is False
    assert result.known_issue is None
    assert result.memout is False
    assert result.exit_code == 1
    assert result.errors == ()


def test_parse_storm_captures_errors(fixture_log: str = "storm_error.log") -> None:
    inv = _inv(fixture_log)
    parse_logfile_storm((FIXTURES / "storm_error.log").read_text(), inv)
    result = inv
    assert len(result.errors) == 2
    assert result.errors[0].startswith(" (UmbImport.cpp:260): The given path")


def test_parse_storm_marks_known_unsupported(fixture_log: str = "storm_unsupported.log") -> None:
    log = (FIXTURES / "storm_success.log").read_text()
    log += "\nERROR (storm-cli.cpp:49): An exception caused Storm to terminate. The message of the exception is: NotSupportedException: Can not build interval model for the provided value type.\n"
    inv = _inv(fixture_log)
    parse_logfile_storm(log, inv)
    assert inv.not_supported is True


def test_parse_storm_marks_known_issue():
    log = (FIXTURES / "storm_success.log").read_text()
    log += "\nERROR (ValueEncoding.h:56): Some values are given as double intervals but a model with a non-interval type is requested.\n"
    inv = _inv("x.log")
    parse_logfile_storm(log, inv)
    assert inv.known_issue is not None


def test_parse_prism_success_is_not_unsupported(fixture_log: str = "prism_success.log") -> None:
    inv = _inv(fixture_log)
    parse_logfile_prism((FIXTURES / "prism_success.log").read_text(), inv)
    assert inv.not_supported is False


def test_parse_prism_marks_unsupported():
    log = (FIXTURES / "prism_success.log").read_text()
    log += "\nError: Unsupported model type TSG in UMB file.\n"
    inv = _inv("x.log")
    parse_logfile_prism(log, inv)
    assert inv.not_supported is True


def test_reported_results_defaults():
    inv = ReportedResults()
    assert inv.exit_code is None
    assert inv.timeout is False
    assert inv.memout is False
    assert inv.not_supported is False
    assert inv.known_issue is None
    assert inv.errors == ()
    assert inv.model_info is None
    assert inv.logfile is None


def test_identifiers():
    assert PrismCLI().identifier == "PrismCLI()"
    assert StormCLI().identifier == "StormCLI()"
    assert ModestCLI().identifier == "ModestCLI()"
    assert PrismCLI(extra_args=["--exact"]).identifier == "PrismCLI(--exact)"
    assert PrismCLI(custom_identifier="Prism").identifier == "Prism"