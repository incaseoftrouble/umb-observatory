import os
from collections.abc import Callable
from typing import cast

import pytest

import umbtest.tools
from umbtest import benchmarks
from umbtest.benchmarks import ChainResults, Tester, UmbBenchmark
from umbtest.outcomes import apply_tolerances
from umbtest.tools import UmbTool

"""
We initialize the tools we use in the tests.
This can also be used to override the standard paths loaded by the configure tools call.
Tools that cannot be executed are skipped rather than crashing collection.

By default the tests run on the small quick benchmark suite. Set
UMB_TEST_MODELS=full to run on all benchmark files.
"""

try:
    umbtest.tools.configure_umbtools()
except FileNotFoundError:
    pass


def _benchmarks() -> list[UmbBenchmark]:
    """Pick the benchmark set used for parametrization."""
    if os.environ.get("UMB_TEST_MODELS") == "full":
        return benchmarks.prism_files
    return benchmarks.quick_prism_files


def modest_cli() -> umbtest.tools.ModestCLI:
    return umbtest.tools.ModestCLI(custom_identifier="Modest")


def _available(tool: UmbTool) -> bool:
    try:
        return bool(tool.check_process())
    except Exception:  # noqa: BLE001
        return False


_availability_cache: dict[tuple[str, tuple[str, ...]], bool] = {}


def _available_cached(tool: UmbTool) -> bool:
    key = (type(tool).__name__, tuple(tool.identifier))
    if key not in _availability_cache:
        _availability_cache[key] = _available(tool)
    return _availability_cache[key]


ToolResult = UmbTool | tuple[UmbTool, UmbTool]


class _ToolSpec:
    def __init__(self, name: str, make: Callable[[], ToolResult]) -> None:
        self._name = name
        self._make = make

    @property
    def identifier(self) -> str:
        return self._name

    def make(self) -> ToolResult:
        return self._make()


def _resolve(spec: _ToolSpec) -> UmbTool:
    result = cast(UmbTool, spec.make())
    if not _available_cached(result):
        pytest.skip(f"{spec.identifier} not available")
    return result


TOOL_SPECS: list[_ToolSpec] = [
    _ToolSpec("Storm", lambda: umbtest.tools.StormCLI(custom_identifier="Storm")),
    _ToolSpec(
        "Storm (exact)",
        lambda: umbtest.tools.StormCLI(extra_args=["--exact"], custom_identifier="Storm (exact)"),
    ),
    _ToolSpec("Prism", lambda: umbtest.tools.PrismCLI(custom_identifier="Prism")),
    _ToolSpec(
        "Prism (exact)",
        lambda: umbtest.tools.PrismCLI(extra_args=["-exact"], custom_identifier="Prism (exact)"),
    ),
]

TOOLPAIR_SPECS: list[_ToolSpec] = [
    _ToolSpec(
        "Prism->Modest",
        lambda: (
            umbtest.tools.PrismCLI(custom_identifier="Prism"),
            umbtest.tools.ModestCLI(custom_identifier="Modest"),
        ),
    ),
]


@pytest.fixture(scope="class", params=TOOL_SPECS, ids=[s.identifier for s in TOOL_SPECS])
def tool(request: pytest.FixtureRequest) -> _ToolSpec:
    return request.param


@pytest.fixture(scope="class", params=TOOLPAIR_SPECS, ids=[s.identifier for s in TOOLPAIR_SPECS])
def toolpair(request: pytest.FixtureRequest) -> _ToolSpec:
    return request.param


umbi_py_umb = umbtest.tools.UmbPython("umb")
umbi_py_ats = umbtest.tools.UmbPython("ats")


def _benchmarkname(val: UmbBenchmark) -> str:
    """
    Helper function to provide better test names.
    :param val:
    :return:
    """
    return str(val.id)


def load_and_read(tester: Tester, benchmark: UmbBenchmark) -> None:
    """
    Tests a tool chain.

    :param tester:
    :param benchmark:
    :return:
    """
    print(f"Testing {tester} on {benchmark}...")
    results: ChainResults = tester.check_benchmark(benchmark)
    apply_tolerances("Loader", results["loader"])
    assert results["loader"].exit_code == 0, "Loader should not crash."
    if results["transformer"] is not None:
        apply_tolerances("Transformer", results["transformer"])
        assert results["transformer"].exit_code == 0, "Transformer should not crash"
    apply_tolerances("Checker", results["checker"])
    assert results["checker"].exit_code == 0, "Checker should not crash."


@pytest.mark.parametrize("tool", TOOL_SPECS, ids=[s.identifier for s in TOOL_SPECS], scope="class")
class TestTool:
    @pytest.mark.parametrize(
        "benchmark", _benchmarks(), ids=_benchmarkname
    )
    def test_write_read(self, tool: _ToolSpec, benchmark: UmbBenchmark) -> None:
        tester = Tester()
        tester.set_chain(loader=_resolve(tool), checker=_resolve(tool))
        load_and_read(tester, benchmark)

    @pytest.mark.parametrize(
        "benchmark", _benchmarks(), ids=_benchmarkname
    )
    def test_write_umbi_umb_read(self, tool: _ToolSpec, benchmark: UmbBenchmark) -> None:
        tester = Tester()
        tester.set_chain(
            loader=_resolve(tool), transformer=umbi_py_umb, checker=_resolve(tool)
        )
        load_and_read(tester, benchmark)

    @pytest.mark.parametrize(
        "benchmark", _benchmarks(), ids=_benchmarkname
    )
    def test_write_umbi_ats_read(self, tool: _ToolSpec, benchmark: UmbBenchmark) -> None:
        tester = Tester()
        tester.set_chain(
            loader=_resolve(tool), transformer=umbi_py_ats, checker=_resolve(tool)
        )
        load_and_read(tester, benchmark)

    @pytest.mark.parametrize(
        "benchmark", _benchmarks(), ids=_benchmarkname
    )
    def test_write_modest_read(self, tool: _ToolSpec, benchmark: UmbBenchmark) -> None:
        tester = Tester()
        tester.set_chain(loader=_resolve(tool), transformer=modest_cli(), checker=_resolve(tool))
        load_and_read(tester, benchmark)


@pytest.mark.parametrize("toolpair", TOOLPAIR_SPECS, ids=[s.identifier for s in TOOLPAIR_SPECS], scope="class")
class TestAlignment:
    @pytest.mark.parametrize(
        "benchmark", _benchmarks(), ids=_benchmarkname
    )
    def test_write_read(self, toolpair: _ToolSpec, benchmark: UmbBenchmark) -> None:
        tester = Tester()
        pair: tuple[UmbTool, UmbTool] = cast(
            tuple[UmbTool, UmbTool], toolpair.make()
        )
        tester.set_chain(loader=pair[0], checker=pair[1])
        load_and_read(tester, benchmark)