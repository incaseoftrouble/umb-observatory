"""Reading-capability regression tests on stored UMB files.

Every model listed in the regression manifest must be readable by umbi and by
each available tool. Sizes are taken from the files themselves: tools must agree with
umbi on the number of states.
A manifest entry can list a tolerated failure per tool via
{"known_issues": {"StormCLI": "reason"}}: the tool is still run, a failure is then
reported as xfail instead of failing the suite, and a success is an ordinary pass.
"""

import tempfile
from pathlib import Path

import pytest
import umbi.ats
import umbi.umb

from umbtest.outcomes import apply_tolerances
from umbtest.regression import load_manifest, model_path
from umbtest.tools import (
    ModestCLI,
    PrismCLI,
    StormCLI,
    UmbTool,
    configure_umbtools,
)

MANIFEST = load_manifest()
NAMES = sorted(MANIFEST)

try:
    configure_umbtools()
except FileNotFoundError:
    pass


def _usable(tool: UmbTool) -> bool:
    try:
        return bool(tool.check_process())
    except Exception:  # noqa: BLE001
        return False


def _num_states(name: str) -> int:
    """The number of states, as declared by the file itself."""
    return umbi.umb.read(model_path(name), strict=True).index.transition_system.num_states


@pytest.mark.skipif(not NAMES, reason="No regression models found")
@pytest.mark.parametrize("name", NAMES)
class TestRegression:
    def test_umbi_umb_reads(self, name: str) -> None:
        umb = umbi.umb.read(model_path(name), strict=True)
        assert umb.index.transition_system.num_states > 0

    def test_umbi_ats_reads(self, name: str) -> None:
        ats = umbi.ats.read(model_path(name), strict=True)
        umb = umbi.umb.read(model_path(name), strict=True)
        assert ats.num_states == umb.index.transition_system.num_states
        assert ats.num_branches == umb.index.transition_system.num_branches

    @pytest.mark.parametrize(
        "tool",
        [StormCLI(), PrismCLI(), ModestCLI()],
        ids=lambda t: t.name,  # pyright: ignore[reportUnknownLambdaType]
    )
    def test_tool_reads(self, name: str, tool: UmbTool) -> None:
        if not _usable(tool):
            pytest.skip(f"{tool.name} not available")
        known_issue = MANIFEST[name].get("known_issues", {}).get(tool.name)
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "read.log"
            result = tool.check_umb(model_path(name), log_file=log)
        apply_tolerances(f"{tool.name} reading {name}", result, known_issue)
        assert result.exit_code == 0, f"{tool.name} failed to read {name}"
        if result.model_info and "states" in result.model_info:
            assert result.model_info["states"] == _num_states(name)
