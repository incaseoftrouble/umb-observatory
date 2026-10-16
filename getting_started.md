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

The unified Markov binary format (UMB) is a file format for probabilistic models such as Markov chains and MDPs. It lists the states and transitions of a model explicitly, rather than describing the model with a program or a modelling language.
Probabilistic model checkers such as Storm, Prism and Modest can read and write it, and the `umbi` Python library can create, read and validate UMB files.
This notebook runs in the UMB Observatory container, which has these tools installed.
We create a model and look at it, look inside the `.umb` file, and then let the tools exchange it.

## Creating a model with umbi
In `umbi`, a model is an annotated transition system (ATS): states have choices, choices have branches that lead to a successor state, and annotations such as probabilities, actions and labels attach information to them.
We build a small MDP (Markov decision process) this way: in each state, a choice selects an action, and the action leads to the next state at random, with given probabilities.
The model has four states. State 0 is initial and chooses between actions `a` and `b`. State 1 has only action `a`, and states 2 and 3 are absorbing. State 3 is labelled `target`.

```{code-cell} ipython3
import umbi

ats = umbi.ats.SimpleAts()
ats.new_states(4)
ats.initial_states = [0]
ats.new_players(1)  # a single player resolves the nondeterminism, making this an MDP

ats.new_choice(state=0, action_name="a", targets=[1, 2], probs=[0.5, 0.5])
ats.new_choice(state=0, action_name="b", targets=[2, 3], probs=[0.2, 0.8])
ats.new_choice(state=1, action_name="a", targets=[0, 1], probs=[0.9, 0.1])
ats.new_choice_absorbing(state=2, action_name="tau")
ats.new_choice_absorbing(state=3, action_name="tau")

ats.new_ap_annotation("target").state_values = [False, False, False, True]
```

We write the model to a `.umb` file and read it back. The counts match the model above: 4 states, 5 choices (one for each action of a state) and 8 branches (one for each possible successor of a choice).

```{code-cell} ipython3
umbi.ats.write(ats, "mdp.umb")
model = umbi.ats.read("mdp.umb")
print(model.num_states, "states,", model.num_choices, "choices,", model.num_branches, "branches")
```

We can look at the model with [Stormvogel](https://stormchecker.github.io/stormvogel/), which reads `.umb` files.
We name the states by their index, so they match the numbers above.

```{code-cell} ipython3
from stormvogel.umbi import read_from_umb
from stormvogel.to_dot import plot_model_pydot

stormvogel_model = read_from_umb("mdp.umb")
for index, state in enumerate(stormvogel_model.states):
    state.set_friendly_name(str(index))
plot_model_pydot(stormvogel_model)
```

## Inspecting the file
A `.umb` file is a tar archive with a single JSON index, `index.json`, and a set of binary `.bin` files.
We start with the index.

```{code-cell} ipython3
import json
import tarfile

with tarfile.open("mdp.umb") as umb_file:
    index = json.load(umb_file.extractfile("index.json"))
print(json.dumps(index, indent=2))
```

The index holds the metadata of the model.
It does not name a model type such as "MDP". Instead, `transition-system` lists the features of the model:
here the numbers of states, choices and branches, and one player, who resolves the nondeterministic choices.
The index also determines which binary files are present: for instance, `#observations` is 0, so there are no observation files.
Annotations, here the atomic proposition `target`, are listed under `annotations`, and each has its own file.

The binary files follow, with their sizes and first bytes.

```{code-cell} ipython3
with tarfile.open("mdp.umb") as umb_file:
    for member in umb_file:
        first_bytes = umb_file.extractfile(member).read(16).hex(" ")
        print(f"{member.name:42} {member.size:3} bytes  {first_bytes}")
```

We can decode the binary files one by one. `umbi.umb.read` returns the content of each file as a plain list, named after the file: `state_to_choices` is the content of `state-to-choices.bin`.

UMB stores the transitions in three layers: states, choices and branches. Each layer is a list of offsets into the next one.
State `s` owns the choices `state_to_choices[s]` up to, but not including, `state_to_choices[s+1]`.
With `[0, 2, 3, 4, 5]`, state 0 owns choices 0 and 1 (the actions `a` and `b`), and states 1, 2 and 3 own one choice each.
In the same way, `choice_to_branches` assigns branches to choices.
A branch has a successor (`branch_to_target`) and a probability (`branch_to_probability`).
Choice 1, action `b`, owns branches 2 and 3: they lead to states 2 and 3, with probabilities 0.2 and 0.8.

Indices are stored as 64-bit unsigned integers and probabilities as 64-bit floating point numbers, both little-endian.

```{code-cell} ipython3
raw = umbi.umb.read("mdp.umb")
for name in ["state_is_initial", "state_to_choices", "choice_to_branches", "branch_to_target",
             "branch_to_probability", "choice_to_choice_action", "choice_action_to_string"]:
    print(f"{name:25}", getattr(raw, name))
```

## Exploring the container
So far we only used `umbi`. The tools that read and write UMB are installed in the container as well, and we can run them from the notebook:

```{code-cell} ipython3
!storm --version | head -n 1
!/opt/prism/prism/bin/prism -version | head -n 1
!/opt/Modest/modest mcsta -Y 2>&1 | head -n 1
```

## Checking the model with the tools
The tools read UMB files directly. We ask each of them for the maximal probability to reach the `target` state.
This is 0.8, by taking action `b` in state 0. Each command filters the tool's output, to keep the key lines.

Storm reads the file with `--explicit-umb`:

```{code-cell} ipython3
!storm --explicit-umb mdp.umb --prop 'Pmax=? [F "target"]' --sound | grep -E "^(Model type|States|Transitions|Choices|Result)"
```

Prism reads it with `-importmodel`:

```{code-cell} ipython3
!/opt/prism/prism/bin/prism -importmodel mdp.umb -pf 'Pmax=? [F "target"]' | grep -E "^(Type|States|Transitions|Result)"
```

Modest reads it with `mcsta -I UMB`. It takes its properties from a file:

```{code-cell} ipython3
!echo 'Pmax(<> target);' > props.txt
!/opt/Modest/modest mcsta -Y mdp.umb props.txt -I UMB | grep -E "States|Choices|Branches|Probability"
```

## Testing tools with umbtest
`umbtest` is the Python package in this repository that checks that the tools agree on UMB. It wraps the command lines of Storm, Prism and Modest, and `umbi`, so the same checks run on all of them. The continuous integration of this repository runs these checks.

A test is a chain: a *loader* turns a model into a UMB file, an optional *transformer* reads and rewrites that file, and a *checker* reads the result. If every step succeeds, the tools agree on the file.

We start by creating the wrappers.

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

Next, we create a `Tester` and give it a chain: Prism is the loader, which exports a model as a UMB file, and Storm is the checker, which reads that file.

```{code-cell} ipython3
from pathlib import Path
from umbtest.benchmarks import Tester

tester = Tester()
tester.set_chain(loader=prism_cli, checker=storm_cli)
```

We run the chain on the dice model that ships with Prism. Prism exports it to UMB, and Storm reads the file and checks the property `R{"coin_flips"}=? [C<=10]`, the expected number of coin flips in the first 10 steps.

```{code-cell} ipython3
result = tester.check_prism_file(Path(prism_cli.prism_dir_path) / "prism-examples/simple/dice/dice.pm", ['R{"coin_flips"}=? [C<=10]'])
```

```{code-cell} ipython3
assert result["checker"].exit_code == 0
assert result["loader"].exit_code == 0
```

Chains can also have a transformer in the middle, here Prism exports, Storm rewrites the file, and Modest reads the result.

```{code-cell} ipython3
tester.set_chain(loader=prism_cli, transformer=storm_cli, checker=modest_cli)
result = tester.check_prism_file(Path(prism_cli.prism_dir_path) / "prism-examples/simple/dice/dice.pm", None)
assert all(result[step].exit_code == 0 for step in ["loader", "transformer", "checker"])
```

The tools can also read the model we created with umbi above.
Their logs show what they loaded: the model type and the numbers of states, choices and branches.
Storm also checks a property, the maximal probability to reach the `target` state. This is 0.8, by taking action `b` in state 0.

```{code-cell} ipython3
storm_cli.check_umb(Path("mdp.umb"), Path("storm.log"), properties=['Pmax=? [F "target"]'])
modest_cli.check_umb(Path("mdp.umb"), Path("modest.log"))

for tool, log in [("Storm", "storm.log"), ("Modest", "modest.log")]:
    print(tool)
    for line in Path(log).read_text().splitlines():
        if line.strip().startswith(("Model type", "States", "Choices", "Branches", "Transitions", "Result", "ERROR", "UMB: error")):
            print("  ", line.strip())
```
