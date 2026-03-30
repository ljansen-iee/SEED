# Industry Methodology

!!! warning "Planned module"
    The `industry/` module is not yet present in this branch.
    `build_pypsa_industry.py` exists as an empty placeholder.
    This page documents the intended methodology.

## Planned sub-sectors

| Sub-sector | Key processes |
|------------|--------------|
| Iron & Steel | BF+BOF, BF+OHF (primary); Scrap EAF (secondary) |
| Chemical & Petrochemical | HVC (naphtha/LPG/methanol cracking) |
| Non-metallic Minerals | Cement dry/wet kilns |
| Paper, Pulp & Printing | Primary (kraft/sulfite) and secondary pulp |
| Food & Tobacco | — |
| Non-ferrous Metals | Aluminium (primary/secondary) |
| Other industries | Mining, construction, textiles, machinery, wood, transport equipment |

## Intended formula

\[
\text{FED}_{\text{sub-sector}} =
  \text{Production} \times \text{Technology share} \times \text{Energy intensity}
  \times \text{Fuel share}
\]

## Data sources (planned)

| Dataset | Sub-sector |
|---------|-----------|
| WorldSteel data | Iron & Steel |
| USGS Mineral Yearbook | Cement |
| FAO STAT | Paper & Pulp |
| UN Comtrade / IFA | Ammonia |
| UNSD Energy Statistics | All (base-year calibration) |
