# Installation

## Prerequisites

- [Conda](https://docs.conda.io/en/latest/) or [Mamba](https://mamba.readthedocs.io/)
  (Mamba is recommended for faster dependency resolution)
- Git

## 1 — Clone the repository

```bash
git clone https://gitlab.cc-asp.fraunhofer.de/gems/sectoral-energy-demands.git
cd sectoral-energy-demands
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
python --version          # Should print Python 3.10.x
python -c "import pandas; print(pandas.__version__)"  # Should print 2.x
```

## Input data

The `data/country_specific/` directory must contain UNSD energy-balance CSVs.
See [Input Data](../data/input-data.md) for download instructions.

## Building the documentation locally

```bash
# Copy visualisation notebooks into the docs tree
cp plots/*.ipynb docs/notebooks/

# Serve with live-reload
mkdocs serve
```

Then open <http://127.0.0.1:8000>.
