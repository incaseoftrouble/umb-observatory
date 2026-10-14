import stat
from pathlib import Path
from typing import TypedDict

import pytest

from umbtest.benchmarks import Tester
from umbtest.tools import ModestCLI, PrismCLI, StormCLI


class StubTools(TypedDict):
    arglog: Path
    storm: StormCLI
    prism: PrismCLI
    modest: ModestCLI


STORM_LOG = (
    "Storm 1.11.1 (dev)\n\n"
    "Command line arguments: --prism x.pm --exportbuild /tmp/x.umb --buildfull -pc\n\n"
    "Time for model construction: 0.004s.\n\n"
    "Model type: \tMDP (sparse)\n"
    "States: \t4\n"
    "Transitions: \t10\n"
    "Choices: \t7\n"
)


def _write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    arglog = tmp_path / "argv.log"

    def _mk_storm():
        _write_script(
            tmp_path / "bin" / "storm",
            f"""echo "storm:${{*}}" >> {arglog}
case "$*" in
  *--version*) echo "Storm 1.11.1 (dev)"; exit 0;;
esac
for a in "$@"; do case "$a" in *.umb) printf 'mock-umb' > "$a";; esac; done
printf '%s' '{STORM_LOG}'
exit 0
""",
        )

    def _mk_prism():
        _write_script(
            tmp_path / "prism" / "prism" / "bin" / "prism",
            f"""echo "prism:${{*}}" >> {arglog}
case "$1" in
  -version) echo "PRISM"; echo "====="; echo "Version: 4.9.dev"; exit 0;;
esac
prev=""
for a in "$@"; do
  case "$a" in
    *.umb) printf 'mock-umb' > "$a";; esac
  if [ "$prev" = "-mainlog" ]; then touch "$a"; fi
  prev="$a"
done
echo "done"
exit 0
""",
        )
        _write_script(
            tmp_path / "prism" / "prism" / "etc" / "scripts" / "prism-log-extract",
            'echo \'"states"\'\necho "4"\nexit 0\n',
        )

    def _mk_modest():
        _write_script(
            tmp_path / "modest",
            f"""echo "modest:${{*}}" >> {arglog}
case "$*" in
  *--version*) echo "Modest 3.0"; exit 0;;
esac
for a in "$@"; do case "$a" in *.umb) printf 'mock-umb' > "$a";; esac; done
exit 0
""",
        )

    _mk_storm()
    _mk_prism()
    _mk_modest()

    return {
        "arglog": arglog,
        "storm": StormCLI(location=tmp_path / "bin" / "storm"),
        "prism": PrismCLI(location=tmp_path / "prism"),
        "modest": ModestCLI(location=tmp_path / "modest"),
    }


def _read_arglog(stub_tools: StubTools) -> str:
    return stub_tools["arglog"].read_text()


def test_storm_check_process(stub_tools: StubTools) -> None:
    assert stub_tools["storm"].check_process() is True
    assert "--version" in _read_arglog(stub_tools)


def test_prism_check_process(stub_tools: StubTools) -> None:
    assert stub_tools["prism"].check_process() is True


def test_modest_check_process(stub_tools: StubTools) -> None:
    assert stub_tools["modest"].check_process() is True


def test_storm_full_roundtrip(stub_tools: StubTools) -> None:
    storm = stub_tools["storm"]
    tester = Tester()
    tester.set_chain(loader=storm, checker=storm)
    results = tester.check_prism_file(Path("/fake/model.nm"), [])
    assert results["loader"].exit_code == 0
    assert results["checker"].exit_code == 0
    assert results["transformer"] is None
    info = results["loader"].model_info
    assert info is not None
    assert info["states"] == 4
    assert info["transitions"] == 10
    log = _read_arglog(stub_tools)
    assert "--exportbuild" in log
    assert "--explicit-umb" in log


def test_prism_full_roundtrip_uses_log_extract(stub_tools: StubTools) -> None:
    prism = stub_tools["prism"]
    tester = Tester()
    tester.set_chain(loader=prism, checker=prism)
    results = tester.check_prism_file(Path("/fake/model.nm"), [])
    assert results["loader"].exit_code == 0
    assert results["checker"].exit_code == 0
    assert results["loader"].model_info == {"states": 4}
    log = _read_arglog(stub_tools)
    assert "-exportmodel" in log
    assert "-importmodel" in log


def test_prism_to_modest_chain(stub_tools: StubTools) -> None:
    tester = Tester()
    tester.set_chain(loader=stub_tools["prism"], checker=stub_tools["modest"])
    results = tester.check_prism_file(Path("/fake/model.nm"), [])
    assert results["loader"].exit_code == 0
    assert results["checker"].exit_code == 0


def test_chain_with_transformer(stub_tools: StubTools) -> None:
    storm = stub_tools["storm"]
    tester = Tester()
    tester.set_chain(loader=storm, transformer=storm, checker=storm)
    results = tester.check_prism_file(Path("/fake/model.nm"), [])
    assert results["loader"].exit_code == 0
    assert results["transformer"] is not None
    assert results["transformer"].exit_code == 0
    assert results["checker"].exit_code == 0