UMB Observatory
=================

This project manages a joint docker file with selected versions of different PMC tools and libraries,
a jupyter server, and a collection of python files that help to ensure that are mutually compatible. 


The container
-------------
Is created from the docker file, released to github daily via CI. 
On the container, you find 
- a version of storm (with UMB support),
- a version of prism (with UMB support),
- the umbi python library.
- the contents of this repo, in particular, the umbtest library.
- A jupyter notebook that is running. 

There are two flavors, built from the same `Dockerfile` (`--build-arg FLAVOR=...`):

| flavor | Storm | umbi | build time |
|---|---|---|---|
| `fast` (default) | prebuilt `movesrwth/storm:stable` image (latest release) | latest release on PyPI | minutes |
| `source` | built from Storm `master` | umbi git `main` | long (Storm compilation) |

Prism is the release binary (v4.11, `PRISM_VERSION` build arg) in `fast` and built from `master`
(`PRISM_REPO`/`PRISM_REF` build args) in `source`. Modest is a downloaded binary: the latest version by default, or the one named by the `MODEST_VERSION` build arg
(e.g. `v3.1.315-g0a0763b35`).

### Running the docker

Two images are published (multi-arch: amd64 and arm64). `ghcr.io/pmc-tools/umb-observatory:main` is the `fast`
flavor, rebuilt daily; `ghcr.io/pmc-tools/umb-observatory:from-source` is the `source` flavor, rebuilt weekly.
Start the notebook:
```
docker run --rm -p 127.0.0.1:8000:8000 -e JUPYTER_TOKEN=umb ghcr.io/pmc-tools/umb-observatory:main
```
and open http://localhost:8000/lab?token=umb. Binding to `127.0.0.1` keeps the notebook reachable only from
your machine. Without `JUPYTER_TOKEN`, the container picks a random token and prints the full URL in its log.
To use a different port, change the first number of `-p`.

To build an image yourself, pick a flavor:
```
docker build -t umb-observatory .                              # fast
docker build --build-arg FLAVOR=source -t umb-observatory:source .
```
Run it like above, with your image name instead of the `ghcr.io` one. Notebooks you create inside the
container are lost when it exits unless you mount a folder, e.g. `-v "$PWD/work:/opt/umb/work"`.

### Connecting to the notebook

Open the URL from the command above (or the one printed in the container log) in your browser.
You can go to `getting_started.ipynb` (in the docker container) to get started
with some opportunities that UMB offers.

The notebook is written in markdown (`getting_started.md`, the tracked source of
truth) and materialized as `.ipynb` when the container image is built. Locally,
regenerate the notebook with:
```
jupytext --to ipynb getting_started.md
```
JupyterLab users can install the jupytext extension to open the `.md` directly.


Umbtest
-------

Umbtest is a set python files that check that UMB support is aligned. 
The best place to get started is probably in `tests/test_toolchains.py`.
Roughly `umbtest/benchmarks.py` collects files we use for testing,
while `umbtest/tools.py` provides a thin layer around the available tools. 

You can use umbtest in different ways. 
The preferred way is via the docker, which ensures that you have the right tools installed in known locations. 

### Via the docker
This is possible in two ways: via a notebook and via the command line. 

#### Via the notebook
As explained in the notebook, to which you can connect as explained above. 

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
UMBTest is currently not available as a standalone package.
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
The Docker image clones it to `/opt/umb-regression` (`REGRESSION_REPO`/`REGRESSION_REF` build args).
Locally, clone it into `regression/` (`git clone https://github.com/pmc-tools/umb-regression.git regression`), or point `UMB_REGRESSION_DIR` at a checkout.
Without it, `tests/test_regression.py` is skipped.

Continuous Integration
-----------------------
This repo is hosted on github, where continuous integration runs Umbtests:
https://github.com/pmc-tools/umb-observatory/actions/workflows/test.yml

