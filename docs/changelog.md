# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added

- MkDocs + Material documentation site (`docs/`, `mkdocs.yml`)
- GitHub Actions workflow for automatic deployment to GitHub Pages (`.github/workflows/docs.yml`)
- Tutorial notebooks for Transport and Residential sectors

### Known issues

See [Known Limitations](index.md#known-limitations) in the README.

---

## [0.1.0] — 2026-03-30

Initial working version with:

- Transport sector: full bottom-up model (mode × vehicle × technology × fuel)
- Residential sector: five end-uses (space heating/cooling, water heating,
  cooking, appliances)
- Additional sectors: Agriculture, Services, Non-energy use, Other
- Root-level cross-sector CAGR and fuel-share computation from UNSD data
- PyPSA energy-totals export for residential + additional sectors
- Visualisation notebooks in `plots/`
