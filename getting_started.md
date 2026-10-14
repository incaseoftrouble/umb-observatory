---
jupytext:
  formats: ipynb,md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.19.2
kernelspec:
  display_name: Python 3 (ipykernel)
  language: python
  name: python3
---

# Getting started

## Exploring the docker
This part of the notebook assumes you are running everything in the associated Docker. It gives you convenient access to the docker container.

### Run Storm
One can run storm

```{code-cell} ipython3
!storm --version
```

### Run Prism

One can also run prism

```{code-cell} ipython3
!/opt/prism/prism/bin/prism
```

### Run Modest

```{code-cell} ipython3
!/opt/Modest/modest
```

## Umbtest
This notebook displays how to get started with testing UMB integration in various tools.

We start by initializing some tools that are already integrated.

```{code-cell} ipython3
from umbtest.tools import PrismCLI, StormCLI, UmbPython, ModestCLI
import umbtest.tools

umbtest.tools.configure_umbtools() # This uses settings from tools.toml!

# We also construct a number of different thin wrappers around existing tools
storm_cli = StormCLI(custom_identifier="Storm")
storm_cli_exact = StormCLI(extra_args = ["--exact"], custom_identifier="Storm (exact)")
prism_cli = PrismCLI(custom_identifier="Prism")
prism_cli_exact = PrismCLI(extra_args = ["-exact"], custom_identifier="Prism (exact)")
modest_cli = ModestCLI(custom_identifier="Modest")
umbi_py_umb = UmbPython("umb")
umbi_py_ats = UmbPython("ats")
```

Next, we set up some test chain that can test interactions between tools supporting UMB.

```{code-cell} ipython3
from pathlib import Path
from umbtest.benchmarks import Tester

tester = Tester()
tester.set_chain(loader=prism_cli, checker=storm_cli)
```

Now, we can rather easily check whether processing a file maintains particular specs.

```{code-cell} ipython3
result = tester.check_prism_file(Path(prism_cli.prism_dir_path) / "prism-examples/simple/dice/dice.pm", ["R=? [F \"one\"]"])
```

```{code-cell} ipython3
assert result["checker"].exit_code == 0
assert result["loader"].exit_code == 0
```

```{code-cell} ipython3

```
