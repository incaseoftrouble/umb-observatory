from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Protocol, TypedDict, cast

from umbtest.tools import PrismCLI, ReportedResults, UmbTool

logger = logging.getLogger(__name__)


class NamedTempFile(Protocol):
    name: str


class UmbBenchmark:
    def __init__(
        self,
        location: Path,
        properties: list[str] | None = None,
        is_prism_file: bool = True,
    ) -> None:
        self.location = location
        self.properties = properties
        self.is_prism_file = is_prism_file

    def __str__(self) -> str:
        return str(self.__dict__)

    @property
    def id(self) -> Path:
        return Path("/".join(self.location.parts[-2:]))


class ChainResults(TypedDict):
    loader: ReportedResults
    checker: ReportedResults
    transformer: ReportedResults | None


def _dump_log(path: Path) -> None:
    with open(path, "r") as f:
        logger.warning("Contents of logfile %s:\n%s", path, f.read())


_prism_files_path = Path(__file__).parent / "../resources/prism-files/"
prism_files: list[UmbBenchmark] = [UmbBenchmark(p) for p in _prism_files_path.glob("*.nm")]

# A small curated suite used by default for quick verification of the
# umbtest tool chains. It spans model types (DTMC/CTMC/MDP), rewards, and the
# known edge cases (e.g. refuel produces a non-standard UMB). The full set
# (prism_files) is used to verify UMB support via UMB_TEST_MODELS=full.
_quick_benchmark_ids: set[str] = {
    "simple1.nm",  # MDP
    "two_dice.nm",  # DTMC
    "csma2-2.nm",  # CTMC
    "tiny_rewards.nm",  # rewards
    "leader3.nm",  # MDP with rewards
    "cluster2.nm",  # MDP
    "polling2.nm",  # MDP
    "tandem5.nm",  # MDP
    "multiobj_team3.nm",  # multi-objective (not supported by all tools)
    "refuel.nm",  # produces a non-standard UMB
}
quick_prism_files: list[UmbBenchmark] = sorted(
    (b for b in prism_files if b.id.name in _quick_benchmark_ids),
    key=lambda b: b.id.name,
)

standard: list[UmbBenchmark] = [
    UmbBenchmark(
        Path(PrismCLI.default_path) / "prism-examples/simple/dice/dice.pm", None
    )
]


class Tester:
    __test__ = False  # not a pytest test class despite the name

    def __init__(
        self,
        id: str | None = None,
        delete_files: bool | None = None,
        testdir: str | tempfile.TemporaryDirectory[str] | None = None,
    ) -> None:
        self._tmpdir = testdir if testdir is not None else tempfile.TemporaryDirectory()
        self._delete_files = True if delete_files is None else delete_files
        self._loader: UmbTool | None = None
        self._checker: UmbTool | None = None
        self._transformer: UmbTool | None = None
        self._id = id

    def _get_tmp_dir_name(self) -> str:
        if isinstance(self._tmpdir, str):
            return self._tmpdir
        return self._tmpdir.name

    def _tmpumbfile(self) -> NamedTempFile:
        return tempfile.NamedTemporaryFile(dir=self._get_tmp_dir_name(), suffix=".umb", delete=self._delete_files, delete_on_close=self._delete_files)

    def _tmplogfile(self) -> NamedTempFile:
        return tempfile.NamedTemporaryFile(dir=self._get_tmp_dir_name(), suffix=".log", delete=self._delete_files, delete_on_close=self._delete_files)

    def set_chain(
        self, loader: UmbTool, checker: UmbTool, transformer: None | UmbTool = None
    ) -> None:
        self._loader = loader
        self._transformer = transformer
        self._checker = checker

    def _require_chain(self) -> tuple[UmbTool, UmbTool]:
        if self._loader is None or self._checker is None:
            raise RuntimeError("You must first set the tool chain, using set_chain()")
        return self._loader, self._checker

    @property
    def id(self) -> str:
        if self._id is None:
            loader, checker = self._require_chain()
            result = f"l={loader.name}"
            if self._transformer is not None:
                result += f"_t={self._transformer.name}"
            else:
                result += "_t=None"
            result += f"_c={checker.name}"
            return result
        else:
            return self._id

    def __str__(self) -> str:
        loader, checker = self._require_chain()
        result = f"load with {loader.name}"
        if self._transformer is not None:
            result += f" transform with {self._transformer.name}"
        result += f" check with {checker.name}"
        return result

    def check_benchmark(self, benchmark: UmbBenchmark) -> ChainResults:
        if benchmark.is_prism_file:
            return self.check_prism_file(benchmark.location, benchmark.properties)
        else:
            raise NotImplementedError("We currently only support prism files")

    def check_prism_file(
        self, prism_file: Path, properties: list[str] | None
    ) -> ChainResults:
        loader, checker = self._require_chain()
        tmpfile_in = self._tmpumbfile()
        tmpfile_in_path = Path(tmpfile_in.name)
        log_file_to_umb = self._tmplogfile()
        result: ChainResults = {
            "loader": loader.prism_file_to_umb(
                prism_file, tmpfile_in_path, log_file=Path(log_file_to_umb.name)
            ),
            "checker": cast(ReportedResults, None),
            "transformer": None,
        }
        if result["loader"].exit_code != 0:
            if result["loader"].logfile is not None:
                _dump_log(result["loader"].logfile)
            if result["loader"].not_supported:
                return result
            if result["loader"].known_issue is None:
                raise RuntimeError(f"Unexpected exception during loading by {loader.name}")
            else:
                return result
        if not tmpfile_in_path.exists() or tmpfile_in_path.stat().st_size == 0:
            if result["loader"].logfile is not None:
                _dump_log(result["loader"].logfile)
            raise RuntimeError(
                f"{loader.name} did not yield a UMB file (but status=0)."
            )
        if self._transformer:
            tmpfile_out = self._tmpumbfile()
            try:
                transformer_result = self._transformer.umb_to_umb(
                    tmpfile_in_path,
                    Path(tmpfile_out.name),
                    log_file=Path(self._tmplogfile().name),
                )
                result["transformer"] = transformer_result
                if transformer_result.exit_code != 0:
                    return result
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"{self._transformer.name} raised {type(e)}:{e}!")
        else:
            tmpfile_out = tmpfile_in
        checker_result = checker.check_umb(
            Path(tmpfile_out.name),
            log_file=Path(self._tmplogfile().name),
            properties=properties,
        )
        result["checker"] = checker_result
        if checker_result.exit_code != 0:
            if checker_result.logfile is not None:
                _dump_log(checker_result.logfile)
            if checker_result.known_issue is not None or checker_result.not_supported:
                return result

        return result