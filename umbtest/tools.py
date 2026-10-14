from __future__ import annotations

import logging
import pathlib
import subprocess
from collections.abc import Callable
from typing import ClassVar, Literal, TypeVar

import umbi

from umbtest.config import load_config

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


#  LOGFILE Parsing
# Taken from and adapted from a project by Alex Bork and Tim Quatmann
def contains_any_of(log: str, msg: list[str]) -> bool:
    for m in msg:
        if m in log:
            return True
    return False


def first_match(log: str, msg: list[str]) -> str | None:
    for m in msg:
        if m in log:
            return m
    return None


def try_parse(
    log: str,
    start: int,
    before: str,
    after: str,
    out_dict: dict[K, V],
    out_key: K,
    out_type: Callable[[str], V],
) -> int:
    pos1 = log.find(before, start)
    if pos1 >= 0:
        pos1 += len(before)
        pos2 = log.find(after, pos1)
        if pos2 >= 0:
            out_dict[out_key] = out_type(log[pos1:pos2])
            return pos2 + len(after)
    return start


def parse_logfile_storm(log: str, inv: ReportedResults) -> None:
    unsupported_messages = [
        "ERROR (storm-cli.cpp:49): An exception caused Storm to terminate. The message of the exception is: NotSupportedException: Can not build interval model for the provided value type."
    ]  # add messages that indicate that the invocation is not supported
    inv.not_supported = contains_any_of(log, unsupported_messages)
    memout_messages: list[str] = []  # add messages that indicate that the invocation is not supported
    memout_messages.append(
        "An unexpected exception occurred and caused Storm to terminate. The message of this exception is: std::bad_alloc"
    )
    memout_messages.append("Return code:\t-9")
    inv.memout = contains_any_of(log, memout_messages)
    known_error_messages = [
        "ERROR (SparseModelFromUmb.cpp:242): Only state observations are currently supported for POMDP models.",
        "ERROR (ValueEncoding.h:56): Some values are given as double intervals but a model with a non-interval type is requested.",
    ]  # add messages that indicate a "known" error, i.e., something that indicates that this is a reported issue.
    inv.known_issue = first_match(log, known_error_messages)
    if inv.not_supported or inv.known_issue is not None:
        return
    if inv.exit_code not in [0, 1]:
        if not inv.timeout and not inv.memout:
            logger.warning(f"Unexpected return code(s): {inv.exit_code}")
        return

    errors: dict[int, str] = {}
    pos = 0
    i = 0
    while i <= 30:
        pos = try_parse(
            log,
            pos,
            "ERROR",
            "\n",
            errors,
            i,
            str,
        )
        if i not in errors:
            break
        i = i + 1
    inv.errors = tuple(errors.values())
    pos = 0
    inv.model_info = {}

    pos = try_parse(
        log,
        pos,
        "Time for model construction: ",
        "s.",
        inv.model_info,
        "model-building-time",
        float,
    )

    pos = try_parse(log, pos, "States: \t", "\n", inv.model_info, "states", int)
    pos = try_parse(
        log, pos, "Transitions: \t", "\n", inv.model_info, "transitions", int
    )
    pos = try_parse(log, pos, "Choices: \t", "\n", inv.model_info, "choices", int)
    pos = try_parse(
        log, pos, "Observations: \t", "\n", inv.model_info, "observations", int
    )


def parse_logfile_prism(log: str, inv: ReportedResults) -> None:
    unsupported_messages = [
        "smg",
        "Error: Explicit engine: Intervals not supported for EXACT.",
        "Error: Unsupported model type TSG in UMB file.",
    ]  # add messages that indicate that the invocation is not supported
    inv.not_supported = contains_any_of(log, unsupported_messages)


def check_tools(*args: UmbTool) -> None:
    for tool in args:
        if not tool.check_process():
            raise RuntimeError(f"Tool '{tool.name}' failed")


def configure_umbtools() -> None:
    tools = load_config()["tools"]
    if "prism" in tools:
        PrismCLI.default_path = tools["prism"]
        logger.warning(
            f"Prism is now configured with default location {PrismCLI.default_path}"
        )
    if "storm" in tools:
        StormCLI.default_path = tools["storm"]
        logger.warning(
            f"Storm is now configured with default location {StormCLI.default_path}"
        )
    if "modest" in tools:
        ModestCLI.default_path = tools["modest"]
        logger.warning(
            f"Modest is now configured with default location {ModestCLI.default_path}"
        )


class UmbTool:
    """Base class for tools that produce or consume UMB files."""

    name: ClassVar[str] = "UmbTool"
    # Abstract placeholder; concrete subclasses must override with a real path.
    default_path: ClassVar[str] = ""

    def __init__(
        self,
        extra_args: list[str] | None = None,
        custom_identifier: str | None = None,
    ) -> None:
        self._extra_args = list(extra_args) if extra_args else []
        self._custom_identifier: str | None = custom_identifier

    @property
    def identifier(self) -> str:
        if self._custom_identifier is not None:
            return self._custom_identifier
        return self.name + "(" + ",".join(self._extra_args) + ")"

    def get_binary_path(self) -> pathlib.Path:
        raise NotImplementedError

    def _invoke(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        invocation = [self.get_binary_path().as_posix()] + args + self._extra_args
        logger.info(f"{self.name} invocation: " + " ".join(invocation))
        return subprocess.run(invocation, capture_output=True, text=True, check=False)

    def check_process(self) -> bool:
        result = self._invoke(["--version"])
        return result.returncode == 0

    def prism_file_to_umb(
        self,
        prism_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path,
    ) -> ReportedResults:
        raise NotImplementedError

    def check_umb(
        self,
        umb_file: pathlib.Path,
        log_file: pathlib.Path | None = None,
        properties: list[str] | None = None,
    ) -> ReportedResults:
        raise NotImplementedError

    def umb_to_umb(
        self,
        input_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path | None,
    ) -> ReportedResults:
        raise NotImplementedError


class ReportedResults:
    def __init__(self) -> None:
        self.timeout: bool = False
        self.memout: bool = False
        self.not_supported: bool = (
            False  # Error messages that say something is not supported.
        )
        # Reason for a failure we tolerate for now (e.g. an already reported issue):
        # the tests report it as xfail instead of failing. None if there is no such issue.
        self.known_issue: str | None = None
        self.errors: tuple[str, ...] = ()
        self.exit_code: int | None = None
        self.model_info: dict[str, int | float] | None = None
        self.logfile: pathlib.Path | None = None

    @classmethod
    def from_subprocess(
        cls,
        result: subprocess.CompletedProcess[str],
        log_file: pathlib.Path | None = None,
    ) -> ReportedResults:
        reported = cls()
        reported.exit_code = result.returncode
        reported.timeout = False
        reported.memout = False
        reported.logfile = log_file
        return reported

    def __str__(self) -> str:
        return f"ReportedResults[{self.logfile},{self.exit_code},{self.model_info},{self.timeout},{self.memout}]"


class PrismCLI(UmbTool):
    default_path: ClassVar[str] = "/opt/prism"
    name: ClassVar[str] = "PrismCLI"

    def __init__(
        self,
        location: str | pathlib.Path | None = None,
        extra_args: list[str] | None = None,
        custom_identifier: str | None = None,
    ) -> None:
        super().__init__(extra_args=extra_args, custom_identifier=custom_identifier)
        self.prism_dir_path = (
            location if location is not None else __class__.default_path
        )

    def get_prism_path(self) -> pathlib.Path:
        path = pathlib.Path(self.prism_dir_path) / "prism/bin/prism"
        if not path.exists():
            raise RuntimeError(f"Prism executable not found at {path}")
        return path

    def get_prism_log_extract_script(self) -> pathlib.Path:
        path = pathlib.Path(self.prism_dir_path) / "prism/etc/scripts/prism-log-extract"
        if not path.exists():
            raise RuntimeError(f"Prism log script not found at {path}")
        return path

    def get_binary_path(self) -> pathlib.Path:
        return self.get_prism_path()

    def _call_prism(
        self, log_file: pathlib.Path | None, args: list[str]
    ) -> ReportedResults:
        args = args + ["-test"] + self._extra_args
        reported_args = args
        if log_file is not None:
            args = ["-mainlog", log_file.as_posix()] + args
        logger.info(" ".join([self.get_prism_path().as_posix()] + reported_args))
        invocation = [self.get_prism_path().as_posix()] + args

        subprocess_result = subprocess.run(
            invocation,
            capture_output=True,
            text=True,
            check=False,
        )
        reported_result = ReportedResults.from_subprocess(subprocess_result, log_file)
        if log_file is not None:
            with open(log_file, "r") as log:
                parse_logfile_prism(log.read(), reported_result)
            log_subprocess_result = subprocess.run(
                [
                    self.get_prism_log_extract_script().as_posix(),
                    "--fields=states",
                    log_file.as_posix(),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if log_subprocess_result.stderr != "":
                logger.warning(
                    "Issues parsing logfile:  " + log_subprocess_result.stderr
                )
            if log_subprocess_result.returncode != 0:
                logger.warning(f"Issues parsing logfile yielded error code {log_subprocess_result.returncode}.")
            data = log_subprocess_result.stdout
            try:
                values = log_subprocess_result.stdout.splitlines()
                if len(values) < 2:
                    raise ValueError("extract returned no data row")
                row = values[1].split(",")
                reported_result.model_info = {
                    "states": int(row[-1]),
                }
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Issues parsing the model info data {data}. Got exception: {e}")
                reported_result.model_info = {}

        return reported_result

    def prism_file_to_umb(
        self,
        prism_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path,
    ) -> ReportedResults:
        return self._call_prism(
            log_file,
            [prism_file.as_posix(), "-exportmodel", output_file.as_posix(), "-ex"],
        )

    def check_umb(
        self,
        umb_file: pathlib.Path,
        log_file: pathlib.Path | None = None,
        properties: list[str] | None = None,
    ) -> ReportedResults:
        return self._call_prism(log_file, ["-importmodel", umb_file.as_posix()])

    def umb_to_umb(
        self,
        input_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path | None,
    ) -> ReportedResults:
        return self._call_prism(
            log_file,
            [
                "-importmodel",
                input_file.as_posix(),
                "-exportmodel",
                output_file.as_posix(),
            ],
        )

    def check_process(self) -> bool:
        result = self._call_prism(None, ["-version"])
        return result.exit_code == 0


class ModestCLI(UmbTool):
    name: ClassVar[str] = "ModestCLI"
    default_path: ClassVar[str] = "/opt/modest"
    empty_properties_file: ClassVar[pathlib.Path] = (
        pathlib.Path(__file__).parent.parent
    ) / "resources" / "empty.properties.txt"

    def __init__(
        self,
        location: str | pathlib.Path | None = None,
        extra_args: list[str] | None = None,
        custom_identifier: str | None = None,
    ) -> None:
        super().__init__(extra_args=extra_args, custom_identifier=custom_identifier)
        self._modest_path = location if location is not None else __class__.default_path

    def get_binary_path(self) -> pathlib.Path:
        path = pathlib.Path(self._modest_path)
        if not path.exists():
            raise RuntimeError(f"Modest executable not found at {path}")
        return path

    def _call_mcsta(
        self, log_file: pathlib.Path | None, args: list[str]
    ) -> ReportedResults:
        invocation = (
            [self.get_binary_path().as_posix(), "mcsta", "-Y"]
            + args
            + self._extra_args
        )
        logger.info("Modest invocation: " + " ".join(invocation))
        result = subprocess.run(
            invocation,
            capture_output=True,
            text=True,
            check=False,
        )
        reported_result = ReportedResults.from_subprocess(result, log_file)
        if log_file is not None:
            with open(log_file, "w+") as log:
                log.write(result.stdout)
                if "error:" in result.stdout:
                    reported_result.exit_code = 1
                if "UMB: error: Only deadlock-free MA, MDP, CTMC, DTMC, and LTS models are supported." in result.stdout:
                    reported_result.not_supported = True
                if "UMB: error: Unsupported" in result.stdout:
                    reported_result.not_supported = True
                if "UMB: error: Models where state 0 is not the initial state are not supported" in result.stdout:
                    reported_result.known_issue = "Modest: models where state 0 is not the initial state are not supported"
                if "UMB: error: Exit rate out of range" in result.stdout:
                    reported_result.known_issue = "Modest: exit rate out of range (e.g. exit rate 0 of an absorbing state)"
                if "UMB: error: Found non-standard file" in result.stdout:
                    reported_result.known_issue = "Modest: found non-standard UMB file"
        return reported_result

    def check_umb(
        self,
        umb_file: pathlib.Path,
        log_file: pathlib.Path | None = None,
        properties: list[str] | None = None,
    ) -> ReportedResults:
        args = [umb_file.as_posix(), __class__.empty_properties_file.as_posix(), "-I", "UMB", "--exhaustive", "-D"]
        if properties is not None and len(properties) > 0:
            raise NotImplementedError("The use of properties is not implemented yet.")
        return self._call_mcsta(log_file, args)

    def umb_to_umb(
        self,
        input_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path | None,
    ) -> ReportedResults:
        assert log_file is not None
        logger.debug(f"Log file for modest transform: {log_file}")
        # Note that output_file must end with .umb for this to work.
        return self._call_mcsta(
            log_file=log_file,
            args=[
                input_file.as_posix(),
                __class__.empty_properties_file.as_posix(),
                "-I", "UMB",
                "--umb",
                output_file.as_posix(),
                "-D",
                "--exhaustive",
            ],
        )

    def check_process(self) -> bool:
        result = self._call_mcsta(None, ["--version"])
        return result.exit_code == 0


class StormCLI(UmbTool):
    name: ClassVar[str] = "StormCLI"
    default_path: ClassVar[str] = "/opt/storm"

    def __init__(
        self,
        location: str | pathlib.Path | None = None,
        extra_args: list[str] | None = None,
        custom_identifier: str | None = None,
    ) -> None:
        super().__init__(extra_args=extra_args, custom_identifier=custom_identifier)
        self._storm_path = location if location is not None else __class__.default_path

    def get_binary_path(self) -> pathlib.Path:
        path = pathlib.Path(self._storm_path)
        if not path.exists():
            raise RuntimeError(f"Storm executable not found at {path}")
        return path

    def _call_storm(
        self, log_file: pathlib.Path | None, args: list[str]
    ) -> ReportedResults:
        invocation = [self.get_binary_path().as_posix()] + args + self._extra_args
        logger.info("Storm invocation: " + " ".join(invocation))
        result = subprocess.run(
            invocation,
            capture_output=True,
            text=True,
            check=False,
        )
        reported_result = ReportedResults.from_subprocess(result, log_file)
        if log_file is not None:
            parse_logfile_storm(result.stdout, reported_result)
            with open(log_file, "w+") as log:
                log.write(result.stdout)
        return reported_result

    def prism_file_to_umb(
        self,
        prism_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path,
    ) -> ReportedResults:
        # Note that output_file must end with .umb for this to work.
        return self._call_storm(
            log_file,
            [
                "--prism",
                prism_file.as_posix(),
                "--exportbuild",
                output_file.as_posix(),
                "--buildfull",
                "-pc",
            ],
        )

    def check_umb(
        self,
        umb_file: pathlib.Path,
        log_file: pathlib.Path | None = None,
        properties: list[str] | None = None,
    ) -> ReportedResults:
        args = ["--explicit-umb", umb_file.as_posix()]
        if properties is not None and len(properties) > 0:
            args += ["--prop", ";".join(properties)]
        return self._call_storm(log_file, args)

    def umb_to_umb(
        self,
        input_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path | None,
    ) -> ReportedResults:
        # Note that output_file must end with .umb for this to work.
        return self._call_storm(
            log_file,
            [
                "--explicit-umb",
                input_file.as_posix(),
                "--exportbuild",
                output_file.as_posix(),
            ],
        )

    def check_process(self) -> bool:
        result = self._call_storm(None, ["--version"])
        return result.exit_code == 0


class UmbPython(UmbTool):
    name = "umbilib"

    def __init__(self, mode: Literal["ats", "umb"] = "umb") -> None:
        """
        :param mode: Either ats or umb
        """
        super().__init__()
        self._mode = mode

    def get_binary_path(self) -> pathlib.Path:
        raise NotImplementedError  # UmbPython runs in-process, no binary.

    def check_process(self) -> bool:
        return True

    def umb_to_umb(
        self,
        input_file: pathlib.Path,
        output_file: pathlib.Path,
        log_file: pathlib.Path | None,
    ) -> ReportedResults:
        if self._mode == "ats":
            ats = umbi.ats.read(input_file, strict=True)
            umbi.ats.write(ats, output_file)
            reported_results = ReportedResults()
            reported_results.exit_code = 0
            reported_results.model_info = {
                "states": ats.num_states,
                "transitions": ats.num_branches,
            }
            return reported_results
        elif self._mode == "umb":
            umb = umbi.umb.read(input_file, strict=True)
            umbi.umb.write(umb, output_file)
            reported_results = ReportedResults()
            reported_results.exit_code = 0
            reported_results.model_info = {
                "states": umb.index.transition_system.num_states,
                "transitions": umb.index.transition_system.num_branches,
            }
            return reported_results
        else:
            raise RuntimeError("Unknown mode")