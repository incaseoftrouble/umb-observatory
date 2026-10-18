UMB Observatory
=================

This repository is a shared test environment for the unified Markov binary format (UMB).
It manages a `Dockerfile` that installs selected versions of probabilistic model checkers (PMC tools) and
libraries that support UMB, a Jupyter notebook server, and the `umbtest` Python package, which checks
that the tools can read the UMB files written by each other.


The container
-------------
The container is built from the `Dockerfile` and published to GitHub by CI (see below).
It contains:
- the probabilistic model checkers Storm, Prism, Modest, and PET, all with UMB support,
- the `umbi` Python library, which creates, reads and validates UMB files,
- the contents of this repository, in particular the `umbtest` package,
- a running Jupyter notebook server with a getting-started notebook.

For drawing models in the notebook, the container also has the Python library
[Stormvogel](https://stormchecker.github.io/stormvogel/) and Graphviz.

There are two flavors, built from the same `Dockerfile` (`--build-arg FLAVOR=...`):

| | `fast` (default) | `source` |
|---|---|---|
| Storm | prebuilt `movesrwth/storm:stable` image (latest release) | built from `master` |
| Prism | release binary v4.11 (`PRISM_VERSION`) | built from `master` (`PRISM_REPO`/`PRISM_REF`) |
| Modest | downloaded binary, latest (or `MODEST_VERSION`) | downloaded binary, latest (or `MODEST_VERSION`) |
| umbi | latest release on PyPI | git `main` |
| build time | minutes | long (Storm compilation) |

### Running the container

Two images are published (multi-arch: amd64 and arm64). `ghcr.io/pmc-tools/umb-observatory:main` is the `fast`
flavor, rebuilt daily; `ghcr.io/pmc-tools/umb-observatory:from-source` is the `source` flavor, rebuilt weekly.
The getting-started notebook runs in both flavors. Start it:
```
docker run --rm -p 127.0.0.1:8000:8000 -e JUPYTER_TOKEN=umb ghcr.io/pmc-tools/umb-observatory:main
```
and open http://localhost:8000/notebooks/getting_started.ipynb?token=umb. Binding to `127.0.0.1` keeps the notebook reachable only from
your machine. Without `JUPYTER_TOKEN`, the container picks a random token and prints the full URL in its log.
To use a different port, change the first number of `-p`.

Notebooks you create inside the container are lost when it exits unless you mount a folder,
e.g. `-v "$PWD/work:/opt/umb/work"`.

#### Connecting to the notebook

Open the URL from the command above (or the one printed in the container log) in your browser.
It opens `getting_started.ipynb`, which gets you started
with some opportunities that UMB offers. For the full file browser, replace `notebooks/getting_started.ipynb` in the URL by `lab`.

The notebook is written in markdown (`getting_started.md`, the tracked source of
truth) and materialized as `.ipynb` when the container image is built. Locally,
regenerate the notebook with:
```
jupytext --to ipynb getting_started.md
```
JupyterLab users can install the jupytext extension to open the `.md` directly.

### Building the container

Pick a flavor:
```
docker build -t umb-observatory .                              # fast
docker build --build-arg FLAVOR=source -t umb-observatory:source .
```
Run the result as above, with your image name instead of the `ghcr.io` one.
To pin a Modest version, add e.g. `--build-arg MODEST_VERSION=v3.1.315-g0a0763b35`.

Umbtest
-------

`umbtest` is a Python package that checks that UMB support is aligned between the tools and `umbi`.
The best place to get started is probably `tests/test_toolchains.py`.
Roughly, `umbtest/benchmarks.py` collects the files we use for testing,
while `umbtest/tools.py` provides a thin layer around the available tools.

You can use `umbtest` in different ways.
The preferred way is via the container, which ensures that you have the right tools installed in known locations.

### Via the container
This is possible in two ways: via the notebook and via the command line.

#### Via the notebook
The section "Checking the tools against each other with umbtest" of the getting-started notebook shows how to chain tools and check a model.
Connect to the notebook as explained above.

#### From the command line
In particular, you can run: 
```
docker run --rm ghcr.io/pmc-tools/umb-observatory:main python -m pytest tests
```
By default the tests run on the small quick benchmark suite (10 models) in
`umbtest.benchmarks.quick_prism_files`. To verify UMB support end-to-end across
all models, run the full suite:
```
docker run --rm -e UMB_TEST_MODELS=full ghcr.io/pmc-tools/umb-observatory:main python -m pytest tests
```
The CI workflow runs the full suite.

### Locally
`umbtest` is currently not available as a standalone package.
However, you can run the scripts directly on your local machine.

1. Configure the tool paths. Copy `tools.toml.example` to `tools.toml` and fill in
   your local installation paths (or set the `UMB_STORM`, `UMB_PRISM`, `UMB_MODEST`
   environment variables). `tools.toml` is not tracked by git.
2. `pip install umbi`
3. - You can run `python -m pytest tests` to run all kind of tests
   - Run `python main.py` for a simple script
   - Or run the python notebook on your local jupyterserver (see above for details)
   - Run `ruff check umbtest tests main.py` and `pyright` for static checks

Regression models
-----------------

The small stored `.umb` files that all tools must be able to read live in a separate repository,
[pmc-tools/umb-regression](https://github.com/pmc-tools/umb-regression), to keep this one small.
The container image clones it to `/opt/umb-regression` (`REGRESSION_REPO`/`REGRESSION_REF` build args).
Locally, clone it into `regression/` (`git clone https://github.com/pmc-tools/umb-regression.git regression`), or point `UMB_REGRESSION_DIR` at a checkout.
Without it, `tests/test_regression.py` is skipped.

Continuous Integration
-----------------------
This repository is hosted on GitHub, where continuous integration
- runs the tests: [test.yml](https://github.com/pmc-tools/umb-observatory/actions/workflows/test.yml),
- publishes the container images: [docker-publish.yml](https://github.com/pmc-tools/umb-observatory/actions/workflows/docker-publish.yml),
- executes the getting-started notebook and publishes it as a web page: [pages.yml](https://github.com/pmc-tools/umb-observatory/actions/workflows/pages.yml).

