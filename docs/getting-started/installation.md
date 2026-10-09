# Installation

## Prerequisites

- [Conda](https://docs.conda.io/en/latest/) or [Mamba](https://mamba.readthedocs.io/)
  (Mamba is recommended for faster dependency resolution)
- Git
- Java 8+ on `PATH` for PDF table extraction via `tabula-py`

## 1 — Clone the repository

```bash
git clone https://github.com/ljansen-iee/SEED.git
cd SEED
```

## 2 — Create the Conda environment

```bash
# With Mamba (faster)
mamba env create -f environment.yaml

# Or with Conda
conda env create -f environment.yaml
```

## 3 — Activate

```bash
conda activate sectoral-energy
```

## 4 — Verify

```bash
python --version
python -c "import numpy, pandas; print(numpy.__version__, pandas.__version__)"
python -c "import tabula; from tabula.io import read_pdf; assert tabula.read_pdf is read_pdf"
java -version
```

The existing pins include Python **3.10.19**, NumPy **2.2.5** and pandas
**2.3.3**. That combination is present and importable in the inspected local
environment; no broad dependency migration is part of this integration. A fresh
Conda solve on every platform has not been certified.

The PDF dependency is **`tabula-py==2.10.0`**, not the unrelated
`tabula==1.0.5` distribution. `tabula-py` supplies both `tabula.read_pdf` and
`tabula.io.read_pdf`; its metadata requires Python >=3.9, NumPy >1.24.4,
pandas >=0.25.3 and `distro` (pinned here to **1.9.0**). These API imports were
checked using an external installation, without changing the project
environment. Existing environments containing the wrong `tabula` distribution
still require reconciliation/recreation from the corrected specification;
changing the YAML alone does not repair an installed environment. Java is a
runtime prerequisite and is not supplied by the pip wrapper.

## Input data

Shared preprocessing reads root
`data/country_specific/UNSD_{Country}-{Year}.csv`. Industry additionally requires
its raw production datasets under `industry/input_data/`; the generator checks
required files before writing. Residential and transport retain their own input
trees and naming conventions. Missing files, source rows, requested dimensions
and readiness evidence must fail, not become fabricated zero demand.
See [Input Data](../data/input-data.md),
[Configuration](../configuration.md) and the [Quick Start](quickstart.md).

## Building the documentation locally

Documentation dependencies are separate from the model environment. Match
the pins in `.github/workflows/docs.yml`:

```bash
python -m pip install mkdocs-material==9.6.7 "mkdocstrings[python]==0.29.1" mkdocs-jupyter==0.25.1
```

CI copies `plots/*.ipynb` into `docs/notebooks/` before building. For a review
build, keep the generated **site directory outside the repository**, rather
than overwriting `public/`. For example, from PowerShell:

```powershell
$site = Join-Path $env:TEMP "sectoral-energy-docs-review"
python -m mkdocs build --site-dir $site
```

!!! warning "Documentation build is BLOCKED by the existing hook reference"
  `mkdocs.yml` references `hooks/ssl_fix.py`, but that file is absent and
  `git show main:hooks/ssl_fix.py` has no file to restore. The integration
  preserves that hook reference, the local GitHub site/repository URLs and
  the existing hosting/SSL configuration. No TLS bypass, replacement hook or
  SSL behavior change is introduced. A configured build/serve remains blocked
  until the owner supplies the intended hook through a separately reviewed
  restoration. Installing the pinned dependencies alone cannot fix this.

After that blocker is resolved, `python -m mkdocs serve` serves the documentation
at <http://127.0.0.1:8000>. A successful documentation build would still not
approve the staged model integration or its blocked emissions for final use.
