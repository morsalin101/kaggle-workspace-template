# Kaggle Workspace Template

Write your notebooks in VS Code. Run them on Kaggle's free GPUs. Never touch the
browser or memorise a `kaggle` CLI flag again.

```bash
git clone https://github.com/<you>/kaggle-workspace-template
cd kaggle-workspace-template

make setup             # asks for your Kaggle key + first project name

make new P=titanic     # scaffold a project
make push P=titanic    # upload + run it on Kaggle
make output P=titanic  # bring the results back
```

One clone holds **many projects** — a classic-ML baseline in one folder, a
deep-learning fine-tune in another — each with its own notebook, its own
settings, and its own Python modules.

---

## Table of contents

- [What you get](#what-you-get)
- [Setup (once)](#setup-once)
- [Your first project](#your-first-project)
- [The daily loop](#the-daily-loop)
- [config.yml — every setting](#configyml--every-setting)
- [Attaching data](#attaching-data)
- [Writing real Python modules](#writing-real-python-modules)
- [Command reference](#command-reference)
- [Repository layout](#repository-layout)
- [How it works under the hood](#how-it-works-under-the-hood)
- [Troubleshooting](#troubleshooting)

---

## What you get

| | |
|---|---|
| **Many projects, one repo** | `projects/<name>/` — separate folders for separate runs. |
| **Readable settings** | GPU, internet, privacy, and attached data live in a commented `config.yml`. No hand-editing JSON. |
| **Real Python modules** | Code in `src/` is uploaded as a private Kaggle dataset and importable in the notebook — so it can be unit-tested locally. |
| **One-word commands** | `make push`, `make status`, `make output`. |
| **Clean git diffs** | The generated `kernel-metadata.json` and the injected bootstrap cell live in `.build/`, never in your tracked files. |
| **Real error messages** | Every config problem is reported at once, in plain English, before anything is uploaded. |

---

## Setup (once)

### 1. Get the repo

Click **"Use this template"** on GitHub (recommended — you get a fresh repo with
no history), or:

```bash
git clone https://github.com/<you>/kaggle-workspace-template
cd kaggle-workspace-template
```

### 2. Get your Kaggle API key

1. Sign in at [kaggle.com](https://www.kaggle.com).
2. Click your avatar → **Settings**.
3. Scroll to **API** → **Create New Token**.
4. A `kaggle.json` file downloads. It contains your username and key.

> **Verify your Kaggle account first.** Phone-verify at
> [kaggle.com/settings](https://www.kaggle.com/settings) — GPU/TPU accelerators
> and internet access are unavailable on unverified accounts.

### 3. Run setup — it asks for everything it needs

```bash
make setup
```

No file editing required. It prompts you:

```
==> Creating virtualenv in .venv/
==> Installing Python dependencies
    dependencies installed
==> Kaggle credentials
    Get them at kaggle.com -> Settings -> API -> Create New Token.
    Tip: you can paste the whole contents of kaggle.json below.

    Kaggle username (or paste kaggle.json): your-name
    Kaggle API key (hidden):
    wrote .env
    wrote /Users/you/.kaggle/kaggle.json
==> Verifying credentials against Kaggle
    authenticated as your-name
==> First project
    Name for a new project (blank to skip): unet
    created projects/unet/

Setup complete.
Write your code in projects/unet/notebook.ipynb, then:
  make push P=unet
```

That single command creates `.venv/`, installs `kaggle` and `PyYAML`, saves your
credentials to both `.env` and `~/.kaggle/kaggle.json` (mode `600`), checks them
against the live API, and scaffolds your first project.

**Shortcut:** at the username prompt you can paste the entire contents of the
`kaggle.json` you just downloaded — `{"username":"...","key":"..."}` — instead
of typing the two fields. The key itself is never echoed to the screen.

Re-running `make setup` is safe: it reuses the credentials it already has rather
than asking again. To enter different ones:

```bash
make setup RECONFIGURE=1
```

**Prefer files over prompts?** Create `.env` first (`cp .env.example .env`) and
setup will use it without asking anything. For CI or scripts:

```bash
make setup NO_INPUT=1              # never prompt; fail if credentials are missing
make setup P=unet NO_INPUT=1       # also scaffold a project, unattended
```

> **You never need to activate the venv.** Every `make` target reaches into
> `.venv/bin/python` directly, and the tool resolves the `kaggle` CLI sitting
> beside that interpreter — so a different `kaggle` earlier on your `PATH`
> (a common leftover from `pip install --user`) can't shadow it.
>
> Prefer to manage your own environment? Skip `.venv` entirely — if it doesn't
> exist, `make` falls back to whatever `python3` is active. Point setup at a
> specific interpreter with `make setup PYTHON=/path/to/python3`.

### Which OS does this work on?

| | Status |
|---|---|
| **macOS** | Works as written. `make` ships with the Xcode command line tools. |
| **Linux** | Works as written. On Debian/Ubuntu you may need `sudo apt install make python3-venv` first. |
| **Windows + WSL** | Works as written — treat it as Linux. **This is the recommended way to use Windows.** |
| **Windows + Git Bash** | Works if you install `make`; the venv layout (`Scripts/` vs `bin/`) is handled. |
| **Windows, native `cmd`/PowerShell** | `make` does not exist. Use the Python CLI directly — see below. |

**Every `make` target is a thin wrapper over the same Python CLI**, so nothing
is lost without `make`. The mapping is one-to-one:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

.venv\Scripts\python -m kwt setup
.venv\Scripts\python -m kwt new unet
.venv\Scripts\python -m kwt add "https://www.kaggle.com/datasets/owner/name" -p unet
.venv\Scripts\python -m kwt push unet
.venv\Scripts\python -m kwt output unet
```

| Make | Python CLI |
|---|---|
| `make new P=unet` | `python -m kwt new unet` |
| `make add P=unet URL=<link>` | `python -m kwt add <link> -p unet` |
| `make push P=unet WAIT=1` | `python -m kwt push unet --wait` |
| `make output P=unet` | `python -m kwt output unet` |
| `make sources P=unet` | `python -m kwt sources unet` |

> `P=` also accepts lowercase `p=`, and `URL=` accepts `url=`.

`.env` is gitignored. **Never commit your key** — if you do, revoke it
immediately with *Expire API Token* on the same settings page.

---

## Your first project

```bash
make new P=titanic
```

That creates:

```
projects/titanic/
├── config.yml        ← every Kaggle setting, commented
├── notebook.ipynb    ← starter notebook, ready to run
├── src/
│   └── titanic_lib.py  ← example module, importable from the notebook
└── outputs/          ← results land here (gitignored)
```

Open `projects/titanic/notebook.ipynb` in VS Code, write your code, then:

```bash
make push P=titanic
```

The first project you create becomes the **default**, so you can drop `P=`
entirely: `make push`. Change the default any time with `make active P=other`.

---

## The daily loop

```bash
# 1. Edit the notebook and src/ modules in VS Code.

# 2. Check the config before spending an upload
make validate P=titanic

# 3. Push and run
make push P=titanic

# 4. Watch it (or use `make run` to push and block until it finishes)
make status P=titanic WATCH=1

# 5. Pull the results down
make output P=titanic
```

Everything the run wrote to `/kaggle/working/` — models, submissions, plots,
plus the execution log — lands in `projects/titanic/outputs/`.

---

## config.yml — every setting

Every knob Kaggle exposes through its API, in one file. Omit any key to accept
its default.

```yaml
title: "Titanic Baseline"   # the name shown on Kaggle
slug: titanic-baseline      # kaggle.com/code/<you>/titanic-baseline

notebook: notebook.ipynb
language: python            # python | r | rmarkdown
kernel_type: notebook       # notebook | script

private: true
accelerator: gpu            # none | gpu | tpu
internet: true

sources:
  datasets: []
  competitions: []
  kernels: []
  models: []

src:
  enabled: true
  dir: src
  include_shared: false
  dataset_slug: null
  dataset_title: null
  inject_bootstrap: true

push:
  wait: false
  poll_interval: 15
  timeout: null

output:
  dir: outputs
```

### Reference

| Key | Default | What it does |
|---|---|---|
| `title` | project name | Display title on Kaggle. |
| `slug` | project name | URL segment. Lowercase, digits, single hyphens, 3–50 chars. Changing it creates a **new** notebook on Kaggle. |
| `notebook` | `notebook.ipynb` | Which file gets pushed. |
| `language` | `python` | `python`, `r`, or `rmarkdown`. |
| `kernel_type` | `notebook` | `notebook` (`.ipynb`) or `script` (`.py`). |
| `private` | `true` | `false` publishes the notebook publicly. |
| `accelerator` | `gpu` | `none`, `gpu`, or `tpu`. See the note below. |
| `internet` | `true` | `false` disables network inside the run — required by some competitions. |
| `sources.datasets` | `[]` | Datasets to attach: `"owner/dataset-slug"`. |
| `sources.competitions` | `[]` | Competition data to attach: `"titanic"`. |
| `sources.kernels` | `[]` | Another notebook's output as input: `"owner/kernel-slug"`. |
| `sources.models` | `[]` | Kaggle Models: `"owner/model/framework/variation/version"`. |
| `src.enabled` | `true` | Turn off if all your code lives in the notebook. |
| `src.dir` | `src` | Folder to upload, relative to the project. |
| `src.include_shared` | `false` | Also bundle the repo-root `shared/` folder. |
| `src.dataset_slug` | `<slug>-src` | Name of the private dataset holding your code. |
| `src.dataset_title` | `<title> — source` | Its display title (6–50 chars). |
| `src.inject_bootstrap` | `true` | Add the `sys.path` cell to the pushed copy. |
| `push.wait` | `false` | Always block until the run finishes. |
| `push.poll_interval` | `15` | Seconds between status checks while waiting. |
| `push.timeout` | `null` | Hard cap on run length, in seconds. |
| `output.dir` | `outputs` | Where `make output` downloads to. |

### Choosing the hardware (GPU T4 ×2, P100, or TPU)

**New projects default to `accelerator: gpu`.** Kaggle's API can only switch the
accelerator **on or off** — the exact hardware is a dropdown in Kaggle's own
notebook editor, not something metadata can express.

If the default is what you want, there is no UI step at all:

```bash
make push P=titanic     # pushes and runs on GPU
```

Verified on a real run: with `accelerator: gpu` and nothing chosen in the UI,
Kaggle provisioned a **Tesla P100-PCIE-16GB**. That is its default.

#### Picking specific hardware (T4 ×2, or a particular TPU)

```bash
make push P=titanic
```

1. `make push` uploads **and immediately starts a run** — the Kaggle API has no
   "upload without running" option.
2. Open the notebook on Kaggle and **cancel that run** so it doesn't eat quota.
3. Pick **GPU T4 ×2** or **TPU VM** in the sidebar.
4. Hit **Save & Run All (Commit)**.

`make status` and `make output P=titanic` still work on that run — it's the same
notebook, so results come back the usual way.

> **Keep `accelerator` set to `gpu` (or `tpu`) in `config.yml` even though you
> pick the hardware in the UI.** `kernel-metadata.json` is authoritative on
> every push: if it says `enable_gpu: false`, the next `make push` switches the
> accelerator back off, whatever you chose in the browser. The *type* is not in
> the metadata, so that part is left alone — but the on/off switch is.

#### If you always want TPU

Skip the UI dance entirely — set it in `config.yml` and push:

```yaml
accelerator: tpu
```

The cancel-and-select routine is only needed to choose a specific *variant*
(T4 ×2 vs P100, or a particular TPU version).

> **Watch your quota.** GPU is roughly 30 hours/week and TPU about 20, both
> reset weekly. Because the default is now `gpu`, a project you meant to run on
> CPU will consume GPU hours — set `accelerator: none` on those.

---

## Attaching data

**The easy way — paste the link.** Copy the dataset's URL out of your browser
and hand it to `make add`:

```bash
make add URL="https://www.kaggle.com/datasets/mahmudulhasantasin/fracatlas-original-dataset"
```

```
  + dataset: mahmudulhasantasin/fracatlas-original-dataset
==> projects/example/config.yml updated
    ...  ->  /kaggle/input/datasets/mahmudulhasantasin/fracatlas-original-dataset

It attaches on the next push:  make push P=example
```

It writes the right slug into the right list in `config.yml`, keeping your
comments intact. Competition, notebook, and model links work the same way — the
link tells `kwt` which kind it is:

```bash
make add URL="https://www.kaggle.com/c/titanic"                          # competition
make add URL="https://www.kaggle.com/code/someone/feature-eng"           # notebook output
make add URL="https://www.kaggle.com/models/google/gemma/pyTorch/7b-it/1" # model
```

Then `make sources` shows everything attached, and `make rm URL=titanic`
detaches by whatever short name you see there.

### The manual way

`make add` only edits `config.yml`, so you can always write it yourself:

```yaml
sources:
  datasets:
    - "zillow/zecon"
    - "your-name/my-private-dataset"
  competitions:
    - "titanic"
  kernels:
    - "someone/feature-engineering"      # use their output as your input
  models:
    - "google/gemma/pyTorch/7b-it/1"
```

**Where to find a slug:** it is the URL tail.
`kaggle.com/datasets/zillow/zecon` → `zillow/zecon`.
`kaggle.com/c/titanic` → `titanic`.

`make validate` checks the shape of every slug before you push, so a typo costs
you a second rather than a failed run.

### Finding your data inside the notebook

Attached data lands under `/kaggle/input`, but **the exact layout is Kaggle's
choice and it has changed over time** — datasets currently mount at
`/kaggle/input/datasets/<owner>/<slug>/`, where they used to sit at
`/kaggle/input/<slug>/`. Don't hardcode either one. Look first:

```python
import os
for root, dirs, files in os.walk('/kaggle/input'):
    print(root, files[:5])
```

Or let the shared helper find it for you (set `src.include_shared: true`):

```python
from shared.env import find_input

data = find_input('zecon')            # works under either layout
df = pd.read_csv(data / 'train.csv')
```

If the slug isn't attached, `find_input` raises an error listing what *is*
attached — much faster than debugging an empty read.

---

## Writing real Python modules

Notebooks are terrible for reusable code. So write it in `src/` instead:

```
projects/titanic/src/titanic_lib.py
```

```python
def load(path):
    import pandas as pd
    return pd.read_csv(path)
```

On `make push`, that folder is uploaded as a **private Kaggle dataset**
(`<you>/titanic-baseline-src`), attached to the notebook, and put on `sys.path`
by a bootstrap cell added to the uploaded copy. That cell *discovers* the mount
point rather than assuming one, so it keeps working when Kaggle moves things
around. In the notebook you just write:

```python
from titanic_lib import load
df = load('/kaggle/input/titanic/train.csv')
```

The same import works locally, so you can unit-test it:

```bash
python -m pytest projects/titanic/src   # or just run it in a scratch notebook
```

Each push creates a new **version** of that dataset, so your code history is
preserved on Kaggle too.

### Sharing code across projects

Put common helpers in the repo-root `shared/` folder and set
`src.include_shared: true`. It arrives importable as `shared.<module>`:

```python
from shared.env import working_dir, on_kaggle

out = working_dir()          # /kaggle/working on Kaggle, ./outputs locally
```

### Opting out

All-in-the-notebook is fine too:

```yaml
src:
  enabled: false
```

No dataset is created and no cell is injected.

---

## Command reference

Run `make` with no arguments to see this list in your terminal.

| Command | What it does |
|---|---|
| `make setup` | Create `.venv`, install deps, ask for credentials + a first project, verify. |
| `make new P=<name>` | Scaffold a new project folder. |
| `make add URL=<link>` | Attach a dataset/competition/model by pasting its Kaggle link. |
| `make rm URL=<link>` | Detach a source, by link or by the short name `make sources` shows. |
| `make sources` | Show everything this project attaches. |
| `make validate P=<name>` | Check the config offline and print the metadata that would be sent. |
| `make push P=<name>` | Sync `src/`, upload the notebook, start the run. |
| `make run P=<name>` | Push and block until the run finishes. |
| `make status P=<name>` | Show the latest run's status. |
| `make output P=<name>` | Download outputs into `projects/<name>/outputs/`. |
| `make pull P=<name>` | Pull the notebook back from Kaggle (edited in the browser?). |
| `make list` | List local projects; `REMOTE=1` also lists your Kaggle notebooks. |
| `make active P=<name>` | Show or set the default project. |
| `make clean` | Delete `.build/`; `OUTPUTS=1` also empties `outputs/`. |
| `make check` | Validate every project at once. |

### Options

| Flag | Applies to | Effect |
|---|---|---|
| `P=<name>` | most | Which project. Defaults to `projects/.active`. |
| `URL=<link>` | `add`, `rm` | A Kaggle link, or a bare `owner/name` slug. |
| `WAIT=1` | `push` | Block until the run finishes. |
| `M="note"` | `push` | Version note for the `src` dataset. |
| `TIMEOUT=<sec>` | `push` | Cap the run's length. |
| `WATCH=1` | `status` | Poll until the run finishes. |
| `FORCE=1` | `pull` | Overwrite the local notebook. |
| `REMOTE=1` | `list` | Also query Kaggle. |
| `OUTPUTS=1` | `clean` | Also empty `outputs/` folders. |

Everything is also reachable directly: `python -m kwt push titanic --wait`.

---

## Repository layout

```
kaggle-workspace-template/
├── Makefile                  the commands
├── README.md                 this file
├── requirements.txt          kaggle + PyYAML
├── .env.example              copy to .env, add your key
├── .kaggle/
│   └── kaggle.json.example   the shape of a Kaggle token file
├── shared/                   code shared by all projects (opt-in per project)
│   └── env.py                on_kaggle(), working_dir(), accelerator()
├── kwt/                      the CLI that wraps the kaggle tool
│   ├── config.py             load + validate config.yml
│   ├── links.py              Kaggle URL -> metadata slug
│   ├── edit.py               patch config.yml without losing comments
│   ├── metadata.py           config.yml -> kernel-metadata.json
│   ├── notebook.py           bootstrap-cell injection
│   ├── srcsync.py            src/ -> private Kaggle dataset
│   ├── scaffold.py           `make new`
│   ├── kaggle_cli.py         subprocess wrapper
│   └── __main__.py           command dispatch
└── projects/
    ├── .active               the default project's name
    └── example/              a working reference project
        ├── config.yml
        ├── notebook.ipynb
        ├── src/
        └── outputs/
```

`.build/` appears when you push. It is scratch space — gitignored, and safe to
delete with `make clean`.

---

## How it works under the hood

`make push` does five things:

1. **Validates** `config.yml` — slugs, enums, source formats, notebook JSON.
   Nothing is uploaded until everything passes.
2. **Syncs `src/`** — stages the folder, then `kaggle datasets create` (first
   time) or `kaggle datasets version` (after that), and waits for Kaggle to
   finish processing it. The dataset is **private**.
3. **Builds `.build/<project>/`** — copies the notebook, injects the bootstrap
   cell into that copy, and renders `kernel-metadata.json` with the `src`
   dataset appended to `dataset_sources`.
4. **Uploads** with `kaggle kernels push`, which also starts the run.
5. **Optionally waits**, polling `kaggle kernels status` until it settles.

Your tracked notebook is never modified. The bootstrap cell only ever exists in
the uploaded copy, so `git diff` stays about your actual work.

---

## Troubleshooting

**`Kaggle credentials not found`**
`cp .env.example .env`, fill in both values, then `make setup`.

**`401 Unauthorized` / `Kaggle rejected your credentials`**
The token was revoked or mistyped. Generate a new one (Settings → API → Create
New Token), update `.env`, re-run `make setup`.

**`403 Forbidden` when attaching a competition**
You must accept that competition's rules on its Kaggle page first.

**GPU or internet quietly unavailable**
Phone-verify your account at [kaggle.com/settings](https://www.kaggle.com/settings).

**`ModuleNotFoundError` for your own module in the notebook**
Check that `src.enabled` is `true` and that the module sits directly inside
`src/`. The bootstrap cell prints `[kwt] warning: dataset ... is not attached`
when it cannot find the upload — that means the dataset didn't attach, not that
the path is wrong. If you disabled `inject_bootstrap`, add the path yourself
(and note the layout: `/kaggle/input/datasets/<you>/<slug>-src`).

**`403` or "You must have write access" on push**
The `slug` in `config.yml` collides with a notebook owned by someone else.
Pick a different slug.

**Your notebook was edited in the browser**
`make pull P=<name> FORCE=1` brings the Kaggle version back down. Delete the
auto-generated bootstrap cell if it comes with it.

**GPU quota exhausted**
Kaggle allows roughly 30 GPU-hours per week, reset weekly. Check your remaining
quota in the notebook editor's sidebar.

---

## License

Use this template however you like.
