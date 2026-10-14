"""Access to the UMB regression models.

The models live in a separate repository (pmc-tools/umb-regression): a
directory with a `manifest.json` and a `models/` folder. It is found through
UMB_REGRESSION_DIR (set in the Docker image) or, by default, a checkout in
`regression/` in this repository (`make regression` clones it there). Without
it, the regression tests are skipped.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict


class RegressionEntry(TypedDict, total=False):
    source: str  # tool (and version) that wrote the file
    known_issues: dict[str, str]  # tool name -> reason; the tool may fail to read this file


def regression_dir() -> Path:
    override = os.environ.get("UMB_REGRESSION_DIR")
    if override:
        return Path(override)
    return Path(__file__).parent.parent / "regression"


def load_manifest() -> dict[str, RegressionEntry]:
    manifest = regression_dir() / "manifest.json"
    if not manifest.exists():
        return {}
    models: dict[str, RegressionEntry] = json.loads(manifest.read_text())["models"]
    return models


def model_path(name: str) -> Path:
    return regression_dir() / "models" / name
